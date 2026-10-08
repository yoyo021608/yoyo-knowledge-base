"""可恢复 Run 的状态机、快照并发控制和事件回放。"""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.agent.errors import (
    AgentRunCancelled,
    AgentRunConflict,
    AgentRunNotFound,
    FinalizationInProgress,
    InvalidAgentInput,
    SnapshotConflict,
)
from server.agent.models import AgentRun, AgentRunEvent, AgentRunSnapshot
from server.agent.types import (
    AgentMode,
    AnswerCitation,
    AnswerResult,
    ContextBudget,
    ContextInput,
    EvidenceStatus,
    ExecutionOptions,
    MessageContext,
    Run,
    RunBundle,
    RunEvent,
    RunSnapshot,
    RunStatus,
    RunStep,
    SearchHitContext,
)
from server.infra.database import Database

_TERMINAL = {"cancelled", "completed", "failed"}
_MODES = {"quick", "research", "comparison", "study"}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(question: str) -> str:
    return hashlib.sha256(question.strip().encode("utf-8")).hexdigest()


def _run_view(value: AgentRun) -> Run:
    return Run(
        id=value.id,
        session_id=value.session_id,
        user_id=value.user_id,
        request_id=value.request_id,
        mode=cast(AgentMode, value.mode),
        status=cast(RunStatus, value.status),
        last_event_seq=value.last_event_seq,
        failure_reason=value.failure_reason,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _hit(data: dict[str, Any]) -> SearchHitContext:
    return SearchHitContext(
        document_id=str(data["document_id"]),
        version_id=str(data["version_id"]),
        title=str(data["title"]),
        content_snippet=str(data["content_snippet"]),
        chunk_id=str(data["chunk_id"]),
        source_url=cast(str | None, data.get("source_url")),
        score=float(data["score"]),
    )


def _context(data: dict[str, Any]) -> ContextInput:
    budget_data = cast(dict[str, Any], data["budget"])
    return ContextInput(
        question=str(data["question"]),
        history=tuple(
            MessageContext(role=cast(Any, item["role"]), content=str(item["content"]))
            for item in cast(list[dict[str, Any]], data["history"])
        ),
        search_hits=tuple(
            _hit(item) for item in cast(list[dict[str, Any]], data["search_hits"])
        ),
        budget=ContextBudget(
            model_window=int(budget_data["model_window"]),
            reserved_output_tokens=int(budget_data["reserved_output_tokens"]),
            safety_margin=int(budget_data["safety_margin"]),
            history_budget=int(budget_data["history_budget"]),
            evidence_budget=int(budget_data["evidence_budget"]),
        ),
    )


def _options(data: dict[str, Any] | None) -> ExecutionOptions:
    if data is None:
        return ExecutionOptions()
    return ExecutionOptions(
        topic_id=cast(str | None, data.get("topic_id")),
        tag=cast(str | None, data.get("tag")),
        document_ids=tuple(cast(list[str], data.get("document_ids", []))),
        version_ids=tuple(cast(list[str], data.get("version_ids", []))),
        user_answer=cast(str | None, data.get("user_answer")),
    )


def _stored_input(context: ContextInput, options: ExecutionOptions) -> str:
    return _json({"context": asdict(context), "options": asdict(options)})


def _answer(raw: str | None) -> AnswerResult | None:
    if raw is None:
        return None
    data = cast(dict[str, Any], json.loads(raw))
    return AnswerResult(
        text=str(data["text"]),
        citations=tuple(
            AnswerCitation(
                document_id=str(item["document_id"]),
                document_version_id=str(item["document_version_id"]),
                chunk_id=str(item["chunk_id"]),
                title_snapshot=str(item["title_snapshot"]),
                source_url=cast(str | None, item.get("source_url")),
                quote=str(item["quote"]),
            )
            for item in cast(list[dict[str, Any]], data["citations"])
        ),
        evidence_status=cast(EvidenceStatus, data["evidence_status"]),
    )


def _snapshot_view(value: AgentRunSnapshot) -> RunSnapshot:
    stored = cast(dict[str, Any], json.loads(value.input_json))
    # 兼容 0005 迁移后已存在、尚未采用 options 包装的运行快照。
    context_data = cast(dict[str, Any], stored.get("context", stored))
    options_data = cast(dict[str, Any] | None, stored.get("options"))
    return RunSnapshot(
        run_id=value.run_id,
        input_message_id=value.input_message_id,
        input=_context(context_data),
        step=cast(RunStep, value.step),
        queries=tuple(cast(list[str], json.loads(value.queries_json))),
        selected_sources=tuple(
            _hit(item)
            for item in cast(
                list[dict[str, Any]], json.loads(value.selected_sources_json)
            )
        ),
        result=_answer(value.result_json),
        mode_result=(
            cast(dict[str, object], json.loads(value.mode_result_json))
            if value.mode_result_json is not None
            else None
        ),
        chat_model=value.chat_model,
        attempt=value.attempt,
        revision=value.revision,
        options=_options(options_data),
    )


def _event(db: Session, run: AgentRun, event_type: str, payload: object) -> None:
    run.last_event_seq += 1
    run.updated_at = datetime.now(UTC)
    db.add(
        AgentRunEvent(
            id=str(uuid4()),
            run_id=run.id,
            event_seq=run.last_event_seq,
            event_type=event_type,
            payload=_json(payload),
        )
    )


def _owned_run(
    db: Session, run_id: str, user_id: str, *, for_update: bool = False
) -> AgentRun:
    statement = select(AgentRun).where(
        AgentRun.id == run_id, AgentRun.user_id == user_id
    )
    if for_update:
        statement = statement.with_for_update()
    value = db.scalar(statement)
    if value is None:
        raise AgentRunNotFound("运行不存在或无权访问")
    return value


def _existing_bundle(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    request_id: str,
    digest: str,
    mode: AgentMode,
    options: ExecutionOptions,
) -> RunBundle | None:
    """读取幂等请求；相同键只能对应同一问题和模式。"""
    existing = db.scalar(
        select(AgentRun).where(
            AgentRun.user_id == user_id,
            AgentRun.session_id == session_id,
            AgentRun.request_id == request_id,
        )
    )
    if existing is None:
        return None
    if existing.question_digest != digest or existing.mode != mode:
        raise AgentRunConflict("相同 request_id 对应的问题或模式不一致")
    snapshot = db.get(AgentRunSnapshot, existing.id)
    if snapshot is None:
        raise AgentRunConflict("运行快照缺失")
    bundle = RunBundle(_run_view(existing), _snapshot_view(snapshot))
    if bundle.snapshot.options != options:
        raise AgentRunConflict("相同 request_id 对应的检索范围或学习答案不一致")
    return bundle


class RunControl:
    """以数据库条件更新保证状态转换、快照和事件顺序一致。"""

    def __init__(self, database: Database, chat_model: str) -> None:
        self._database = database
        self._chat_model = chat_model

    def create_run(
        self,
        session_id: str,
        user_id: str,
        request_id: str,
        mode: AgentMode,
        input_value: ContextInput,
        options: ExecutionOptions | None = None,
    ) -> RunBundle:
        execution_options = options or ExecutionOptions()
        if mode not in _MODES or not all(
            value.strip()
            for value in (session_id, user_id, request_id, input_value.question)
        ):
            raise InvalidAgentInput("会话、用户、请求标识、模式和问题必须有效")
        digest = _digest(input_value.question)
        request_key = request_id.strip()
        try:
            with self._database.transaction() as db:
                existing = _existing_bundle(
                    db,
                    session_id=session_id,
                    user_id=user_id,
                    request_id=request_key,
                    digest=digest,
                    mode=mode,
                    options=execution_options,
                )
                if existing is not None:
                    return existing
                now = datetime.now(UTC)
                run = AgentRun(
                    id=str(uuid4()),
                    session_id=session_id,
                    user_id=user_id,
                    request_id=request_key,
                    mode=mode,
                    status="queued",
                    question_digest=digest,
                    created_at=now,
                    updated_at=now,
                )
                db.add(run)
                db.flush()
                snapshot = AgentRunSnapshot(
                    run_id=run.id,
                    input_json=_stored_input(input_value, execution_options),
                    step="rewrite",
                    queries_json="[]",
                    selected_sources_json="[]",
                    chat_model=self._chat_model,
                    attempt=0,
                    revision=0,
                )
                db.add(snapshot)
                _event(db, run, "run.created", {"status": "queued", "mode": mode})
        except IntegrityError:
            # 两个请求同时首创同一幂等键时，唯一约束胜者提交后复用其 Run。
            with self._database.session() as db:
                existing = _existing_bundle(
                    db,
                    session_id=session_id,
                    user_id=user_id,
                    request_id=request_key,
                    digest=digest,
                    mode=mode,
                    options=execution_options,
                )
                if existing is None:
                    raise
                return existing
        return RunBundle(_run_view(run), _snapshot_view(snapshot))

    def get(self, run_id: str, user_id: str) -> RunBundle:
        with self._database.session() as db:
            run = _owned_run(db, run_id, user_id)
            snapshot = db.get(AgentRunSnapshot, run.id)
            if snapshot is None:
                raise AgentRunConflict("运行快照缺失")
            return RunBundle(_run_view(run), _snapshot_view(snapshot))

    def execute_run(
        self, run_id: str, user_id: str, input_message_id: str
    ) -> RunBundle:
        if not input_message_id.strip():
            raise InvalidAgentInput("输入消息标识不能为空")
        with self._database.transaction() as db:
            run = _owned_run(db, run_id, user_id, for_update=True)
            if run.status == "cancelled":
                raise AgentRunCancelled("运行已取消")
            if run.status in {"completed", "failed", "finalizing"}:
                raise AgentRunConflict("当前运行状态不能重新执行")
            snapshot = db.get(AgentRunSnapshot, run.id)
            if snapshot is None:
                raise AgentRunConflict("运行快照缺失")
            if snapshot.input_message_id not in {None, input_message_id}:
                raise AgentRunConflict("运行绑定的输入消息不一致")
            if run.status == "running":
                raise AgentRunConflict("运行正在由其他执行者处理")
            run.status = "running"
            snapshot.input_message_id = input_message_id
            _event(db, run, "run.started", {"input_message_id": input_message_id})
        return RunBundle(_run_view(run), _snapshot_view(snapshot))

    def save_snapshot(
        self, snapshot: RunSnapshot, expected_revision: int, event_type: str
    ) -> RunSnapshot:
        with self._database.transaction() as db:
            run = db.scalar(
                select(AgentRun).where(AgentRun.id == snapshot.run_id).with_for_update()
            )
            if run is None:
                raise AgentRunNotFound("运行不存在")
            if run.status == "cancelled":
                raise AgentRunCancelled("运行已取消")
            if run.status not in {"running", "paused"}:
                raise AgentRunConflict("当前运行状态不能保存执行快照")
            stored = db.get(AgentRunSnapshot, snapshot.run_id)
            if stored is None:
                raise AgentRunConflict("运行快照缺失")
            result = db.execute(
                update(AgentRunSnapshot)
                .where(
                    AgentRunSnapshot.run_id == snapshot.run_id,
                    AgentRunSnapshot.revision == expected_revision,
                )
                .values(
                    input_message_id=snapshot.input_message_id,
                    input_json=_stored_input(snapshot.input, snapshot.options),
                    step=snapshot.step,
                    queries_json=_json(snapshot.queries),
                    selected_sources_json=_json(
                        [asdict(value) for value in snapshot.selected_sources]
                    ),
                    result_json=(
                        _json(asdict(snapshot.result))
                        if snapshot.result is not None
                        else None
                    ),
                    mode_result_json=(
                        _json(snapshot.mode_result)
                        if snapshot.mode_result is not None
                        else None
                    ),
                    chat_model=snapshot.chat_model,
                    attempt=snapshot.attempt,
                    revision=expected_revision + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            changed = cast(Any, result).rowcount
            if changed != 1:
                raise SnapshotConflict("运行快照已被其他执行者更新")
            _event(
                db,
                run,
                event_type,
                {"step": snapshot.step, "revision": expected_revision + 1},
            )
            db.flush()
            refreshed = db.get(AgentRunSnapshot, snapshot.run_id)
            assert refreshed is not None
            return _snapshot_view(refreshed)

    def cancel(self, run_id: str, user_id: str) -> Run:
        with self._database.transaction() as db:
            run = _owned_run(db, run_id, user_id, for_update=True)
            if run.status == "finalizing":
                raise FinalizationInProgress("最终回答正在保存，不能取消")
            if run.status == "cancelled":
                return _run_view(run)
            if run.status in {"completed", "failed"}:
                raise AgentRunConflict("终态运行不能取消")
            run.status = "cancelled"
            _event(db, run, "run.cancelled", {"status": "cancelled"})
        return _run_view(run)

    def pause_interrupted(self, run_id: str) -> None:
        with self._database.transaction() as db:
            run = db.scalar(
                select(AgentRun).where(AgentRun.id == run_id).with_for_update()
            )
            if run is not None and run.status in {"queued", "running"}:
                run.status = "paused"
                _event(db, run, "run.paused", {"reason": "executor_interrupted"})

    def continue_run(self, run_id: str, user_id: str) -> Run:
        with self._database.transaction() as db:
            run = _owned_run(db, run_id, user_id, for_update=True)
            if run.status != "paused":
                raise AgentRunConflict("只有暂停的运行可以继续")
            snapshot = db.get(AgentRunSnapshot, run.id)
            if snapshot is None:
                raise AgentRunConflict("运行快照缺失")
            if snapshot.step == "generate" and snapshot.result_json is None:
                snapshot.attempt += 1
                _event(
                    db, run, "generation.interrupted", {"attempt": snapshot.attempt - 1}
                )
            run.status = "queued"
            _event(db, run, "run.continued", {"attempt": snapshot.attempt})
        return _run_view(run)

    def begin_finalize(self, run_id: str, user_id: str) -> Run:
        with self._database.transaction() as db:
            run = _owned_run(db, run_id, user_id, for_update=True)
            snapshot = db.get(AgentRunSnapshot, run.id)
            if run.status == "finalizing":
                return _run_view(run)
            if run.status == "cancelled":
                raise AgentRunCancelled("运行已取消")
            if (
                run.status != "running"
                or snapshot is None
                or snapshot.result_json is None
            ):
                raise AgentRunConflict("只有已生成完整结果的运行可以提交")
            run.status = "finalizing"
            _event(db, run, "run.finalizing", {"status": "finalizing"})
        return _run_view(run)

    def complete(self, run_id: str, user_id: str) -> Run:
        with self._database.transaction() as db:
            run = _owned_run(db, run_id, user_id, for_update=True)
            if run.status == "completed":
                return _run_view(run)
            if run.status != "finalizing":
                raise AgentRunConflict("运行尚未取得最终提交权")
            run.status = "completed"
            _event(db, run, "run.completed", {"status": "completed"})
        return _run_view(run)

    def fail(self, run_id: str, user_id: str, reason: str) -> Run:
        if not reason.strip():
            raise InvalidAgentInput("失败原因不能为空")
        with self._database.transaction() as db:
            run = _owned_run(db, run_id, user_id, for_update=True)
            if run.status == "failed" and run.failure_reason == reason.strip():
                return _run_view(run)
            if run.status in {"cancelled", "completed", "finalizing"}:
                raise AgentRunConflict("当前运行状态不能标记失败")
            run.status = "failed"
            run.failure_reason = reason.strip()
            _event(db, run, "run.failed", {"reason": run.failure_reason})
        return _run_view(run)

    def read_events(
        self, run_id: str, user_id: str, after_seq: int = 0, limit: int = 100
    ) -> tuple[RunEvent, ...]:
        if after_seq < 0 or not 1 <= limit <= 500:
            raise InvalidAgentInput("事件序号或读取数量无效")
        with self._database.session() as db:
            _owned_run(db, run_id, user_id)
            values = db.scalars(
                select(AgentRunEvent)
                .where(
                    AgentRunEvent.run_id == run_id,
                    AgentRunEvent.event_seq > after_seq,
                )
                .order_by(AgentRunEvent.event_seq)
                .limit(limit)
            ).all()
            return tuple(
                RunEvent(
                    id=value.id,
                    run_id=value.run_id,
                    event_seq=value.event_seq,
                    event_type=value.event_type,
                    payload=value.payload,
                    created_at=value.created_at,
                )
                for value in values
            )

    def list_recoverable(self, limit: int = 100) -> tuple[Run, ...]:
        if not 1 <= limit <= 1000:
            raise InvalidAgentInput("扫描数量必须在 1 到 1000 之间")
        with self._database.session() as db:
            values = db.scalars(
                select(AgentRun)
                .where(
                    AgentRun.status.in_(("queued", "running", "paused", "finalizing"))
                )
                .order_by(AgentRun.updated_at)
                .limit(limit)
            ).all()
            return tuple(_run_view(value) for value in values)

    def list_terminal(self, limit: int = 1000) -> tuple[Run, ...]:
        """供恢复协调清理终态 Run 遗留的会话领取关系。"""
        if not 1 <= limit <= 1000:
            raise InvalidAgentInput("扫描数量必须在 1 到 1000 之间")
        with self._database.session() as db:
            values = db.scalars(
                select(AgentRun)
                .where(AgentRun.status.in_(tuple(_TERMINAL)))
                .order_by(AgentRun.updated_at.desc())
                .limit(limit)
            ).all()
            return tuple(_run_view(value) for value in values)

    def recover_interrupted(self, limit: int = 1000) -> int:
        """启动时暂停失去执行者的 queued/running Run，等待客户端显式继续。"""
        values = self.list_recoverable(limit)
        interrupted = [
            value for value in values if value.status in {"queued", "running"}
        ]
        for value in interrupted:
            self.pause_interrupted(value.id)
        return len(interrupted)

    def purge_session_runs(self, session_id: str, user_id: str) -> None:
        with self._database.transaction() as db:
            values = db.scalars(
                select(AgentRun)
                .where(AgentRun.session_id == session_id, AgentRun.user_id == user_id)
                .with_for_update()
            ).all()
            for run in values:
                if run.status not in _TERMINAL:
                    run.status = "cancelled"
                    _event(db, run, "run.cancelled", {"reason": "session_deleted"})
            db.flush()
            db.execute(
                delete(AgentRun).where(
                    AgentRun.session_id == session_id, AgentRun.user_id == user_id
                )
            )
