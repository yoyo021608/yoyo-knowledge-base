"""会话生命周期与活动 Run 互斥；不处理 Agent 的运行状态。"""

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from server.infra.database import Database
from server.sessions.errors import (
    InvalidSessionInput,
    SessionBusy,
    SessionDeleting,
    SessionNotFound,
)
from server.sessions.models import ConversationSession
from server.sessions.types import SessionStatus, SessionView


def _view(value: ConversationSession) -> SessionView:
    return SessionView(
        id=value.id,
        user_id=value.user_id,
        name=value.name,
        status=cast(SessionStatus, value.status),
        active_run_id=value.active_run_id,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def require_session(db: Session, session_id: str, user_id: str) -> ConversationSession:
    value = db.scalar(
        select(ConversationSession).where(
            ConversationSession.id == session_id, ConversationSession.user_id == user_id
        )
    )
    if value is None:
        raise SessionNotFound("会话不存在或无权访问")
    return value


class SessionManagement:
    """维护会话本身，并用 active_run_id 防止同一会话并发提问。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, user_id: str, name: str = "新会话") -> SessionView:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise InvalidSessionInput("会话名称长度必须为 1 到 120 个字符")
        now = datetime.now(UTC)
        value = ConversationSession(
            id=str(uuid4()),
            user_id=user_id,
            name=clean_name,
            status="active",
            created_at=now,
            updated_at=now,
        )
        with self._database.transaction() as db:
            db.add(value)
        return _view(value)

    def list(self, user_id: str) -> tuple[SessionView, ...]:
        with self._database.session() as db:
            values = db.scalars(
                select(ConversationSession)
                .where(ConversationSession.user_id == user_id)
                .order_by(ConversationSession.updated_at.desc())
            ).all()
            return tuple(_view(value) for value in values)

    def get(self, session_id: str, user_id: str) -> SessionView:
        with self._database.session() as db:
            return _view(require_session(db, session_id, user_id))

    def rename(self, session_id: str, user_id: str, name: str) -> SessionView:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise InvalidSessionInput("会话名称长度必须为 1 到 120 个字符")
        with self._database.transaction() as db:
            value = require_session(db, session_id, user_id)
            if value.status == "deleting":
                raise SessionDeleting("会话正在删除")
            value.name = clean_name
            value.updated_at = datetime.now(UTC)
        return _view(value)

    def try_claim_run(self, session_id: str, user_id: str, run_id: str) -> None:
        if not run_id.strip():
            raise InvalidSessionInput("run_id 不能为空")
        with self._database.transaction() as db:
            value = require_session(db, session_id, user_id)
            if value.status == "deleting":
                raise SessionDeleting("会话正在删除")
            if value.active_run_id == run_id:
                return
            if value.active_run_id is not None:
                raise SessionBusy("会话已有正在执行的任务")
            claimed_id = db.scalar(
                update(ConversationSession)
                .where(
                    ConversationSession.id == session_id,
                    ConversationSession.user_id == user_id,
                    ConversationSession.status == "active",
                    ConversationSession.active_run_id.is_(None),
                )
                .values(active_run_id=run_id, updated_at=datetime.now(UTC))
                .returning(ConversationSession.id)
            )
            if claimed_id is None:
                # 条件更新可能输给了并发的同一 Run；同一 Run 重试仍应成功。
                claimed_by = db.scalar(
                    select(ConversationSession.active_run_id).where(
                        ConversationSession.id == session_id,
                        ConversationSession.user_id == user_id,
                    )
                )
                if claimed_by == run_id:
                    return
                raise SessionBusy("会话已有正在执行的任务")

    def release_run(self, session_id: str, user_id: str, run_id: str) -> None:
        with self._database.transaction() as db:
            value = db.scalar(
                select(ConversationSession).where(
                    ConversationSession.id == session_id,
                    ConversationSession.user_id == user_id,
                )
            )
            if value is None:
                return
            # 旧 Run 的迟到释放不能清掉后续 Run 的关联。
            if value.active_run_id == run_id:
                value.active_run_id = None
                value.updated_at = datetime.now(UTC)

    def begin_delete(self, session_id: str, user_id: str) -> None:
        with self._database.transaction() as db:
            value = require_session(db, session_id, user_id)
            value.status = "deleting"
            value.updated_at = datetime.now(UTC)

    def list_deleting(self, limit: int = 100) -> tuple[SessionView, ...]:
        if not 1 <= limit <= 1000:
            raise InvalidSessionInput("扫描数量必须在 1 到 1000 之间")
        with self._database.session() as db:
            values = db.scalars(
                select(ConversationSession)
                .where(ConversationSession.status == "deleting")
                .order_by(ConversationSession.updated_at)
                .limit(limit)
            ).all()
            return tuple(_view(value) for value in values)

    def delete(self, session_id: str, user_id: str) -> None:
        """只完成 sessions 数据清理；controller 应先让 agent 清理活动 Run。"""
        with self._database.transaction() as db:
            value = db.scalar(
                select(ConversationSession).where(
                    ConversationSession.id == session_id,
                    ConversationSession.user_id == user_id,
                )
            )
            if value is None:
                return
            if value.status != "deleting":
                raise InvalidSessionInput("必须先将会话标记为删除中")
            if value.active_run_id is not None:
                raise SessionBusy("活动任务尚未清理")
            db.execute(
                delete(ConversationSession).where(ConversationSession.id == session_id)
            )
