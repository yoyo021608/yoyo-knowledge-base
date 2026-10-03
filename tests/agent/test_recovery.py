"""验证跨模块恢复能补偿最终保存、残留关联和两阶段删除。"""

from collections.abc import Iterator

import pytest

from server.agent.module import AgentModule
from server.agent.types import (
    ContextInput,
    ExecutionOptions,
    RetrievalPlan,
    SearchHitContext,
)
from server.config import Settings
from server.controller.agent.recovery import recover_pending
from server.infra.chat import FakeChatClient
from server.infra.database import Base, Database
from server.sessions.errors import SessionNotFound
from server.sessions.module import SessionsModule


class RecoveryDocumentsPort:
    def search(self, user_id: str, plan: RetrievalPlan) -> tuple[SearchHitContext, ...]:
        del user_id, plan
        return (SearchHitContext("d1", "v1", "资料", "可恢复证据", "c1", None, 0.9),)

    def validate_sources(
        self,
        user_id: str,
        hits: tuple[SearchHitContext, ...],
        *,
        allow_historical_versions: bool = False,
    ) -> tuple[SearchHitContext, ...]:
        del user_id, allow_historical_versions
        return hits


@pytest.fixture
def recovery_context() -> Iterator[tuple[Database, AgentModule, SessionsModule]]:
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    agent = AgentModule.create(
        database, settings, FakeChatClient(), RecoveryDocumentsPort()
    )
    sessions = SessionsModule.create(database)
    yield database, agent, sessions
    database.close()


def _input(agent: AgentModule) -> ContextInput:
    return ContextInput("如何恢复", (), (), agent.default_budget)


def test_recovery_releases_terminal_link_and_finishes_deleting_session(
    recovery_context: tuple[Database, AgentModule, SessionsModule],
) -> None:
    _database, agent, sessions = recovery_context
    terminal_session = sessions.management.create("u1", "终态残留")
    terminal = agent.runs.create_run(
        terminal_session.id, "u1", "terminal", "quick", _input(agent)
    )
    sessions.management.try_claim_run(terminal_session.id, "u1", terminal.run.id)
    agent.runs.cancel(terminal.run.id, "u1")

    deleting_session = sessions.management.create("u1", "待删除")
    deleting = agent.runs.create_run(
        deleting_session.id, "u1", "deleting", "quick", _input(agent)
    )
    sessions.management.try_claim_run(deleting_session.id, "u1", deleting.run.id)
    sessions.management.begin_delete(deleting_session.id, "u1")

    assert recover_pending(agent, sessions) >= 2
    assert sessions.management.get(terminal_session.id, "u1").active_run_id is None
    with pytest.raises(SessionNotFound):
        sessions.management.get(deleting_session.id, "u1")


def test_recovery_reclaims_and_persists_finalizing_run(
    recovery_context: tuple[Database, AgentModule, SessionsModule],
) -> None:
    _database, agent, sessions = recovery_context
    session = sessions.management.create("u1", "最终保存")
    created = agent.runs.create_run(
        session.id, "u1", "finalizing", "quick", _input(agent)
    )
    sessions.management.try_claim_run(session.id, "u1", created.run.id)
    user_message = sessions.history.append_user(
        session.id, "u1", created.run.id, "如何恢复"
    )
    running = agent.runs.execute_run(created.run.id, "u1", user_message.id)
    agent.workflows.execute(running, "u1", ExecutionOptions())
    agent.runs.begin_finalize(created.run.id, "u1")
    # 模拟异常处理已释放关联，但进程在回答写入前退出。
    sessions.management.release_run(session.id, "u1", created.run.id)

    assert recover_pending(agent, sessions) == 1
    assert agent.runs.get(created.run.id, "u1").run.status == "completed"
    assert sessions.management.get(session.id, "u1").active_run_id is None
    assert [item.role for item in sessions.history.list(session.id, "u1")] == [
        "user",
        "assistant",
    ]
