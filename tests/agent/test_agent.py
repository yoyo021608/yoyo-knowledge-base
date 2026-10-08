"""验证 Agent 的模块边界、状态恢复和四模式共用编排基础。"""

import json
from collections.abc import Iterator
from dataclasses import replace

import pytest

from server.agent.errors import AgentRunCancelled, AgentRunConflict, InvalidAgentInput
from server.agent.module import AgentModule
from server.agent.rag.context import ContextAssembler
from server.agent.rag.retrieval import RetrievalOrchestrator
from server.agent.types import (
    ContextBudget,
    ContextInput,
    ExecutionOptions,
    MessageContext,
    RetrievalPlan,
    SearchHitContext,
    ToolCall,
)
from server.config import Settings
from server.infra.chat import FakeChatClient
from server.infra.database import Base, Database


class FakeDocumentsPort:
    def __init__(self) -> None:
        self.plans: list[RetrievalPlan] = []
        self.historical_flags: list[bool] = []
        self.hits: tuple[SearchHitContext, ...] = (
            SearchHitContext(
                "d1", "v1", "资料一", "Python 是编程语言", "c1", None, 0.9
            ),
            SearchHitContext(
                "d2", "v2", "资料二", "Python 支持类型标注", "c2", None, 0.8
            ),
        )

    def search(self, user_id: str, plan: RetrievalPlan) -> tuple[SearchHitContext, ...]:
        assert user_id == "u1"
        self.plans.append(plan)
        selected = self.hits
        if plan.document_ids:
            selected = tuple(
                item for item in selected if item.document_id in plan.document_ids
            )
        return selected

    def validate_sources(
        self,
        user_id: str,
        hits: tuple[SearchHitContext, ...],
        *,
        allow_historical_versions: bool = False,
    ) -> tuple[SearchHitContext, ...]:
        self.historical_flags.append(allow_historical_versions)
        assert user_id == "u1"
        valid = {
            (item.document_id, item.version_id, item.chunk_id): item
            for item in self.hits
        }
        return tuple(
            replace(item, content_snippet=valid[key].content_snippet)
            for item in hits
            if (key := (item.document_id, item.version_id, item.chunk_id)) in valid
        )


@pytest.fixture
def agent() -> Iterator[tuple[AgentModule, FakeDocumentsPort, Database]]:
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    settings = Settings(
        llm_provider="fake",
        database_url="sqlite+pysqlite:///:memory:",
    )
    documents = FakeDocumentsPort()
    value = AgentModule.create(database, settings, FakeChatClient(), documents)
    yield value, documents, database
    database.close()


def _input(agent: AgentModule, question: str = "Python 是什么") -> ContextInput:
    return ContextInput(
        question=question,
        history=(MessageContext("user", "我们正在学习 Python"),),
        search_hits=(),
        budget=agent.default_budget,
    )


def test_run_is_idempotent_and_rejects_changed_question(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, _documents, _database = agent
    first = module.runs.create_run("s1", "u1", "request-1", "quick", _input(module))
    same = module.runs.create_run("s1", "u1", "request-1", "quick", _input(module))
    assert same.run.id == first.run.id
    with pytest.raises(AgentRunConflict):
        module.runs.create_run(
            "s1", "u1", "request-1", "quick", _input(module, "另一个问题")
        )


def test_run_persists_execution_scope_and_rejects_changed_scope(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, _documents, _database = agent
    options = ExecutionOptions(topic_id="topic-1", tag="python")
    created = module.runs.create_run(
        "s1", "u1", "request-scope", "research", _input(module), options
    )

    assert module.runs.get(created.run.id, "u1").snapshot.options == options
    with pytest.raises(AgentRunConflict):
        module.runs.create_run(
            "s1",
            "u1",
            "request-scope",
            "research",
            _input(module),
            ExecutionOptions(topic_id="topic-2", tag="python"),
        )


def test_quick_workflow_persists_recoverable_steps(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, _documents, _database = agent
    created = module.runs.create_run("s1", "u1", "request-2", "quick", _input(module))
    running = module.runs.execute_run(created.run.id, "u1", "message-1")
    output = module.workflows.execute(running, "u1", ExecutionOptions())
    saved = module.runs.get(created.run.id, "u1")
    assert saved.snapshot.step == "generate"
    assert saved.snapshot.result == output.answer
    assert output.answer.evidence_status == "sufficient"
    assert {item.chunk_id for item in output.answer.citations} == {"c1", "c2"}
    assert [
        item.event_seq for item in module.runs.read_events(created.run.id, "u1")
    ] == list(range(1, saved.run.last_event_seq + 1))


def test_comparison_passes_selected_scope_to_documents(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, documents, _database = agent
    created = module.runs.create_run(
        "s1", "u1", "request-3", "comparison", _input(module)
    )
    running = module.runs.execute_run(created.run.id, "u1", "message-2")
    output = module.workflows.execute(
        running,
        "u1",
        ExecutionOptions(document_ids=("d1", "d2")),
    )
    assert documents.plans[-1].document_ids == ("d1", "d2")
    assert output.answer.evidence_status == "sufficient"
    assert output.mode_result is not None


def test_comparison_explicit_versions_allow_historical_sources(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, documents, _database = agent
    created = module.runs.create_run(
        "s1", "u1", "request-history", "comparison", _input(module)
    )
    running = module.runs.execute_run(created.run.id, "u1", "message-history")
    module.workflows.execute(
        running,
        "u1",
        ExecutionOptions(version_ids=("v1", "v2")),
    )
    assert documents.plans[-1].version_ids == ("v1", "v2")
    assert documents.historical_flags[-1] is True


def test_study_result_uses_evidence_overlap_instead_of_answer_wording(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, _documents, _database = agent
    created = module.runs.create_run(
        "s1", "u1", "request-study", "study", _input(module)
    )
    running = module.runs.execute_run(created.run.id, "u1", "message-study")
    output = module.workflows.execute(
        running,
        "u1",
        ExecutionOptions(user_answer="Python 是编程语言"),
    )
    assert output.mode_result is not None
    assert output.mode_result["verdict"] == "correct"
    assert float(output.mode_result["automatic_score"]) >= 0.6


def test_context_budget_counts_evidence_headers_and_message_overhead() -> None:
    packet = ContextAssembler().build(
        ContextInput(
            question="问题",
            history=(),
            search_hits=(
                SearchHitContext(
                    "d", "v", "很长的证据标题", "证据正文", "c", None, 1.0
                ),
            ),
            budget=ContextBudget(80, 10, 10, 10, 12),
        ),
        "system",
    )
    assert packet.input_tokens <= 60


def test_document_tool_ignores_model_supplied_user_identity(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, documents, _database = agent
    result = module.tools.execute(
        "u1",
        ToolCall(
            "search_documents",
            json.dumps({"query": "Python", "user_id": "attacker"}),
        ),
    )
    assert result.success is True
    assert documents.plans[-1].query == "Python"

    invalid = module.tools.execute(
        "u1",
        ToolCall(
            "search_documents",
            json.dumps({"query": "Python", "document_ids": "d1"}),
        ),
    )
    assert invalid.success is False
    assert "document_ids" in invalid.error_message


def test_retrieval_plan_rejects_out_of_range_limit(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    _module, documents, _database = agent
    with pytest.raises(InvalidAgentInput):
        RetrievalOrchestrator(documents).plan("Python", limit=51)


def test_cancel_blocks_snapshot_write(
    agent: tuple[AgentModule, FakeDocumentsPort, Database],
) -> None:
    module, _documents, _database = agent
    created = module.runs.create_run("s1", "u1", "request-4", "quick", _input(module))
    running = module.runs.execute_run(created.run.id, "u1", "message-3")
    module.runs.cancel(created.run.id, "u1")
    with pytest.raises(AgentRunCancelled):
        module.runs.save_snapshot(
            replace(running.snapshot, queries=("Python",)),
            running.snapshot.revision,
            "rewrite.completed",
        )
