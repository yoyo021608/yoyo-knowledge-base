"""四种产品模式的编排；知识读取和结果保存仍通过边界端口完成。"""

import re
import time
from dataclasses import replace

from server.agent.answering import AnswerGenerator
from server.agent.evaluation import RunEvaluator
from server.agent.ports import DocumentSearchPort
from server.agent.prompts import (
    ANSWER_SYSTEM_PROMPT,
    COMPARISON_SYSTEM_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    STUDY_SYSTEM_PROMPT,
)
from server.agent.rag import (
    ContextAssembler,
    EvidenceAssessor,
    QuestionRewriter,
    RetrievalOrchestrator,
)
from server.agent.rag.text import tokens
from server.agent.run_control import RunControl
from server.agent.types import (
    ExecutionOptions,
    RewriteInput,
    RunBundle,
    SearchHitContext,
    WorkflowOutput,
)


class AgentWorkflows:
    def __init__(
        self,
        runs: RunControl,
        rewriter: QuestionRewriter,
        retrieval: RetrievalOrchestrator,
        evidence: EvidenceAssessor,
        context: ContextAssembler,
        answers: AnswerGenerator,
        evaluator: RunEvaluator,
        documents: DocumentSearchPort,
        *,
        max_retries: int,
        retrieval_timeout_seconds: float,
    ) -> None:
        self._runs = runs
        self._rewriter = rewriter
        self._retrieval = retrieval
        self._evidence = evidence
        self._context = context
        self._answers = answers
        self._evaluator = evaluator
        self._documents = documents
        self._max_retries = max_retries
        self._retrieval_timeout_seconds = retrieval_timeout_seconds

    def execute(
        self, bundle: RunBundle, user_id: str, options: ExecutionOptions
    ) -> WorkflowOutput:
        """从持久化步骤继续执行，已完成的检索结果可以直接复用。"""
        snapshot = bundle.snapshot
        if snapshot.result is not None:
            return WorkflowOutput(
                snapshot.result,
                self._evaluator.evaluate(snapshot.selected_sources, snapshot.result),
                snapshot.mode_result,
            )
        rewritten = self._rewriter.rewrite(
            RewriteInput(snapshot.input.question, snapshot.input.history)
        )
        if not snapshot.queries:
            snapshot = self._runs.save_snapshot(
                replace(snapshot, step="rewrite", queries=(rewritten.text,)),
                snapshot.revision,
                "rewrite.completed",
            )

        if snapshot.selected_sources:
            hits = snapshot.selected_sources
        else:
            hits, queries = self._retrieve_for_mode(
                bundle.run.mode, rewritten.text, user_id, options
            )
            snapshot = self._runs.save_snapshot(
                replace(
                    snapshot,
                    step="retrieve",
                    queries=queries,
                    selected_sources=hits,
                    input=replace(snapshot.input, search_hits=hits),
                ),
                snapshot.revision,
                "retrieval.completed",
            )

        # 生成前复核版本和访问状态，失效片段不能进入最终回答。
        allow_historical = bundle.run.mode == "comparison" and bool(options.version_ids)
        validated = self._documents.validate_sources(
            user_id,
            hits,
            allow_historical_versions=allow_historical,
        )
        if len(validated) < len(hits):
            # 来源在生成前失效时只补查一轮，并继续沿用原模式的范围约束。
            refresh_plan = self._retrieval.plan(
                rewritten.text,
                topic_id=options.topic_id,
                tag=options.tag,
                document_ids=(
                    options.document_ids if bundle.run.mode == "comparison" else ()
                ),
                version_ids=(
                    options.version_ids if bundle.run.mode == "comparison" else ()
                ),
                limit=12 if bundle.run.mode in {"research", "comparison"} else 8,
            )
            refreshed = self._documents.validate_sources(
                user_id,
                self._retrieval.retrieve(refresh_plan, user_id),
                allow_historical_versions=allow_historical,
            )
            valid_by_key = {
                (item.document_id, item.version_id, item.chunk_id): item
                for item in (*validated, *refreshed)
            }
            validated = tuple(
                sorted(valid_by_key.values(), key=lambda value: -value.score)[:24]
            )
        decision = self._evidence.assess(snapshot.input.question, validated)
        if bundle.run.mode == "comparison":
            compared = {(item.document_id, item.version_id) for item in validated}
            if len(compared) < 2:
                decision = replace(
                    decision,
                    sufficient=False,
                    reason="指定范围内少于两个可比较的文档版本",
                )
        if not decision.sufficient:
            answer = self._answers.insufficient()
        else:
            generation_input = snapshot.input
            if bundle.run.mode == "study" and options.user_answer is not None:
                generation_input = replace(
                    generation_input,
                    question=(
                        f"练习题：{snapshot.input.question}\n"
                        f"用户答案：{options.user_answer}\n"
                        "请依据证据判断答案并解释薄弱知识点。"
                    ),
                )
            packet = self._context.build(
                replace(generation_input, search_hits=validated),
                self._prompt_for(bundle.run.mode),
            )
            answer = self._answers.generate(packet)

        evaluation = self._evaluator.evaluate(validated, answer)
        mode_result = self._mode_result(
            bundle.run.mode,
            snapshot.input.question,
            validated,
            answer.text,
            options,
        )
        self._runs.save_snapshot(
            replace(
                snapshot,
                step="generate",
                selected_sources=validated,
                result=answer,
                mode_result=mode_result,
            ),
            snapshot.revision,
            "generation.completed",
        )
        return WorkflowOutput(answer, evaluation, mode_result)

    def _retrieve_for_mode(
        self,
        mode: str,
        question: str,
        user_id: str,
        options: ExecutionOptions,
    ) -> tuple[tuple[SearchHitContext, ...], tuple[str, ...]]:
        started = time.monotonic()
        queries = (
            self._research_queries(question) if mode == "research" else (question,)
        )
        hits: list[SearchHitContext] = []
        completed_queries: list[str] = []
        for query in queries:
            attempt = 0
            current = query
            while True:
                if time.monotonic() - started > self._retrieval_timeout_seconds:
                    break
                plan = self._retrieval.plan(
                    current,
                    topic_id=options.topic_id,
                    tag=options.tag,
                    document_ids=options.document_ids if mode == "comparison" else (),
                    version_ids=options.version_ids if mode == "comparison" else (),
                    limit=12 if mode in {"research", "comparison"} else 8,
                )
                current_hits = self._retrieval.retrieve(plan, user_id)
                hits.extend(current_hits)
                completed_queries.append(current)
                decision = self._evidence.assess(query, tuple(current_hits))
                next_step = self._evidence.next_retrieval(
                    query,
                    tuple(completed_queries),
                    decision,
                    attempt,
                    self._max_retries,
                )
                if not next_step.retry:
                    break
                attempt += 1
                current = next_step.query
        unique = {
            (item.document_id, item.version_id, item.chunk_id): item for item in hits
        }
        selected = tuple(sorted(unique.values(), key=lambda value: -value.score)[:24])
        return selected, tuple(completed_queries)

    @staticmethod
    def _research_queries(question: str) -> tuple[str, ...]:
        parts = tuple(
            value.strip()
            for value in re.split(r"[？?；;。]", question)
            if value.strip()
        )
        return parts[:4] or (question,)

    @staticmethod
    def _prompt_for(mode: str) -> str:
        return {
            "quick": ANSWER_SYSTEM_PROMPT,
            "research": RESEARCH_SYSTEM_PROMPT,
            "comparison": COMPARISON_SYSTEM_PROMPT,
            "study": STUDY_SYSTEM_PROMPT,
        }[mode]

    @staticmethod
    def _mode_result(
        mode: str,
        question: str,
        hits: tuple[SearchHitContext, ...],
        answer: str,
        options: ExecutionOptions,
    ) -> dict[str, object] | None:
        source_ids = [item.chunk_id for item in hits]
        if mode == "research":
            subquestions = AgentWorkflows._research_queries(question)
            unresolved = [
                value
                for value in subquestions
                if not AgentWorkflows._question_supported(value, hits)
            ]
            return {
                "report": answer,
                "subquestions": list(subquestions),
                "unresolved_questions": unresolved,
                "evidence_status": "partial" if unresolved else "sufficient",
                "source_chunk_ids": source_ids,
            }
        if mode == "comparison":
            evidence_by_version: dict[str, list[str]] = {}
            for item in hits:
                key = f"{item.document_id}:{item.version_id}"
                evidence_by_version.setdefault(key, []).append(item.chunk_id)
            return {
                "summary": answer,
                "document_ids": list(options.document_ids),
                "version_ids": list(options.version_ids),
                "evidence_by_version": evidence_by_version,
                "compared_scope_count": len(evidence_by_version),
                "source_chunk_ids": source_ids,
            }
        if mode == "study":
            if options.user_answer is None:
                return {
                    "exercise": answer,
                    "evaluation_status": "awaiting_answer",
                    "source_chunk_ids": source_ids,
                }
            overlap = AgentWorkflows._answer_overlap(options.user_answer, hits)
            if not hits:
                verdict = "insufficient_evidence"
            elif overlap >= 0.6:
                verdict = "correct"
            elif overlap >= 0.25:
                verdict = "partial"
            else:
                verdict = "incorrect"
            return {
                "question": question,
                "user_answer": options.user_answer,
                "verdict": verdict,
                "automatic_score": round(overlap, 4),
                "explanation": answer,
                "mastery": {
                    "status": verdict,
                    "source_chunk_ids": source_ids,
                    "basis": "用户答案与已校验证据的关键词覆盖率",
                },
            }
        return None

    @staticmethod
    def _question_supported(question: str, hits: tuple[SearchHitContext, ...]) -> bool:
        expected = set(tokens(question))
        if not expected:
            return bool(hits)
        evidence = set(token for item in hits for token in tokens(item.content_snippet))
        return len(expected & evidence) / len(expected) >= 0.2

    @staticmethod
    def _answer_overlap(user_answer: str, hits: tuple[SearchHitContext, ...]) -> float:
        answer_tokens = set(tokens(user_answer))
        if not answer_tokens:
            return 0.0
        evidence_tokens = set(
            token for item in hits for token in tokens(item.content_snippet)
        )
        return len(answer_tokens & evidence_tokens) / len(answer_tokens)
