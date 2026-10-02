"""研究、对比、练习和反馈等已产生结果的保存与回放。"""

import json
from typing import cast
from uuid import uuid4

from sqlalchemy import select

from server.infra.database import Database
from server.sessions.errors import (
    IdempotencyConflict,
    InvalidSessionInput,
    ResultNotFound,
    SessionDeleting,
)
from server.sessions.management import require_session
from server.sessions.models import (
    Citation,
    Feedback,
    InteractionResult,
    Message,
    PracticeRecord,
)
from server.sessions.types import (
    FeedbackTarget,
    FeedbackView,
    InteractionResultView,
    PracticeRecordView,
    ResultKind,
    TaskStatus,
)


def _result_view(value: InteractionResult) -> InteractionResultView:
    return InteractionResultView(
        id=value.id,
        session_id=value.session_id,
        run_id=value.run_id,
        kind=cast(ResultKind, value.kind),
        question=value.question,
        status=cast(TaskStatus, value.status),
        result_json=value.result_json,
        failure_reason=value.failure_reason,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _practice_view(value: PracticeRecord) -> PracticeRecordView:
    return PracticeRecordView(
        id=value.id,
        session_id=value.session_id,
        run_id=value.run_id,
        question=value.question,
        answer=value.answer,
        verdict=value.verdict,
        explanation=value.explanation,
        mastery_snapshot_json=value.mastery_snapshot_json,
        created_at=value.created_at,
    )


def _feedback_view(value: Feedback) -> FeedbackView:
    return FeedbackView(
        id=value.id,
        session_id=value.session_id,
        target_type=cast(FeedbackTarget, value.target_type),
        target_id=value.target_id,
        rating=value.rating,
        comment=value.comment,
        created_at=value.created_at,
    )


def _json(data: object) -> str:
    try:
        return json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise InvalidSessionInput("结果快照必须能够序列化为 JSON") from exc


class InteractionResults:
    """只持久化 Agent 产出的结果，不生成研究计划、比较结论或练习题。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save_task(
        self,
        session_id: str,
        user_id: str,
        run_id: str,
        kind: str,
        question: str,
        status: TaskStatus,
        result: object | None = None,
        failure_reason: str | None = None,
    ) -> InteractionResultView:
        if kind not in {"research", "comparison"} or not question.strip():
            raise InvalidSessionInput("结果类型或问题无效")
        if status == "completed" and result is None:
            raise InvalidSessionInput("完成的任务必须包含结果")
        payload = _json(result) if result is not None else None
        with self._database.transaction() as db:
            owner = require_session(db, session_id, user_id)
            existing = db.scalar(
                select(InteractionResult).where(
                    InteractionResult.session_id == session_id,
                    InteractionResult.run_id == run_id,
                    InteractionResult.kind == kind,
                )
            )
            if existing is not None:
                if existing.question != question.strip():
                    raise IdempotencyConflict("相同 Run 的任务问题不一致")
                terminal = {"completed", "failed", "cancelled"}
                if existing.status in terminal:
                    if (
                        existing.status,
                        existing.result_json,
                        existing.failure_reason,
                    ) != (
                        status,
                        payload,
                        failure_reason,
                    ):
                        raise IdempotencyConflict("已结束的任务结果不能改写")
                    return _result_view(existing)
                if (
                    existing.status == status
                    and existing.result_json == payload
                    and existing.failure_reason == failure_reason
                ):
                    return _result_view(existing)
            if owner.status == "deleting":
                raise SessionDeleting("会话正在删除，不能写入结果")
            if owner.active_run_id != run_id:
                raise IdempotencyConflict("当前 Run 未领取该会话")
            if existing is not None:
                allowed = {
                    "queued": {"queued", "running", "completed", "failed", "cancelled"},
                    "running": {"running", "completed", "failed", "cancelled"},
                }
                if status not in allowed[existing.status]:
                    raise IdempotencyConflict("任务状态不能倒退")
                existing.status = status
                existing.result_json = payload
                existing.failure_reason = failure_reason
                return _result_view(existing)
            value = InteractionResult(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
                kind=kind,
                question=question.strip(),
                status=status,
                result_json=payload,
                failure_reason=failure_reason,
            )
            db.add(value)
        return _result_view(value)

    def list_tasks(
        self, session_id: str, user_id: str
    ) -> tuple[InteractionResultView, ...]:
        with self._database.session() as db:
            require_session(db, session_id, user_id)
            values = db.scalars(
                select(InteractionResult)
                .where(InteractionResult.session_id == session_id)
                .order_by(InteractionResult.created_at)
            ).all()
            return tuple(_result_view(value) for value in values)

    def save_practice(
        self,
        session_id: str,
        user_id: str,
        run_id: str,
        question: str,
        answer: str,
        verdict: str,
        explanation: str,
        mastery_snapshot: object,
    ) -> PracticeRecordView:
        if not all(value.strip() for value in (question, answer, verdict, explanation)):
            raise InvalidSessionInput("练习记录字段不能为空")
        snapshot = _json(mastery_snapshot)
        with self._database.transaction() as db:
            owner = require_session(db, session_id, user_id)
            existing = db.scalar(
                select(PracticeRecord).where(
                    PracticeRecord.session_id == session_id,
                    PracticeRecord.run_id == run_id,
                )
            )
            if existing is not None:
                expected = (
                    question.strip(),
                    answer.strip(),
                    verdict.strip(),
                    explanation.strip(),
                    snapshot,
                )
                actual = (
                    existing.question,
                    existing.answer,
                    existing.verdict,
                    existing.explanation,
                    existing.mastery_snapshot_json,
                )
                if actual != expected:
                    raise IdempotencyConflict("相同 Run 的练习记录不一致")
                return _practice_view(existing)
            if owner.status == "deleting":
                raise SessionDeleting("会话正在删除，不能写入练习")
            if owner.active_run_id != run_id:
                raise IdempotencyConflict("当前 Run 未领取该会话")
            value = PracticeRecord(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
                question=question.strip(),
                answer=answer.strip(),
                verdict=verdict.strip(),
                explanation=explanation.strip(),
                mastery_snapshot_json=snapshot,
            )
            db.add(value)
        return _practice_view(value)

    def list_practice(
        self, session_id: str, user_id: str
    ) -> tuple[PracticeRecordView, ...]:
        with self._database.session() as db:
            require_session(db, session_id, user_id)
            values = db.scalars(
                select(PracticeRecord)
                .where(PracticeRecord.session_id == session_id)
                .order_by(PracticeRecord.created_at)
            ).all()
            return tuple(_practice_view(value) for value in values)

    def save_feedback(
        self,
        session_id: str,
        user_id: str,
        target_type: FeedbackTarget,
        target_id: str,
        rating: int,
        comment: str = "",
    ) -> FeedbackView:
        if rating not in {-1, 1}:
            raise InvalidSessionInput("反馈评分只能是 -1 或 1")
        with self._database.transaction() as db:
            require_session(db, session_id, user_id)
            # 验证目标归属，避免用反馈接口探测或评价其他用户的数据。
            if target_type in {"message", "citation"}:
                if target_type == "message":
                    owned = db.scalar(
                        select(Message.id).where(
                            Message.id == target_id,
                            Message.user_id == user_id,
                            Message.session_id == session_id,
                        )
                    )
                else:
                    owned = db.scalar(
                        select(Citation.id)
                        .join(Message, Message.id == Citation.message_id)
                        .where(
                            Citation.id == target_id,
                            Citation.user_id == user_id,
                            Message.session_id == session_id,
                        )
                    )
            else:
                owned = db.scalar(
                    select(PracticeRecord.id).where(
                        PracticeRecord.id == target_id,
                        PracticeRecord.user_id == user_id,
                        PracticeRecord.session_id == session_id,
                    )
                )
            if owned is None:
                raise ResultNotFound("反馈目标不存在或无权访问")
            existing = db.scalar(
                select(Feedback).where(
                    Feedback.user_id == user_id,
                    Feedback.target_type == target_type,
                    Feedback.target_id == target_id,
                )
            )
            if existing is not None:
                existing.rating = rating
                existing.comment = comment.strip()
                value = existing
            else:
                value = Feedback(
                    id=str(uuid4()),
                    session_id=session_id,
                    user_id=user_id,
                    target_type=target_type,
                    target_id=target_id,
                    rating=rating,
                    comment=comment.strip(),
                )
                db.add(value)
        return _feedback_view(value)

    def list_feedback(self, session_id: str, user_id: str) -> tuple[FeedbackView, ...]:
        with self._database.session() as db:
            require_session(db, session_id, user_id)
            values = db.scalars(
                select(Feedback)
                .where(Feedback.session_id == session_id, Feedback.user_id == user_id)
                .order_by(Feedback.created_at)
            ).all()
            return tuple(_feedback_view(value) for value in values)
