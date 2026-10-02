"""消息和引用快照的原子保存与按用户回放。"""

from typing import cast
from uuid import uuid4

from sqlalchemy import select

from server.infra.database import Database
from server.sessions.errors import (
    IdempotencyConflict,
    InvalidSessionInput,
    MessageNotFound,
    SessionDeleting,
)
from server.sessions.management import require_session
from server.sessions.models import Citation, Message
from server.sessions.types import CitationInput, CitationView, MessageRole, MessageView


def _citation_view(value: Citation) -> CitationView:
    return CitationView(
        id=value.id,
        message_id=value.message_id,
        document_id=value.document_id,
        document_version_id=value.document_version_id,
        chunk_id=value.chunk_id,
        title_snapshot=value.title_snapshot,
        quote=value.quote,
        source_url=value.source_url,
    )


def _message_view(value: Message, citations: tuple[CitationView, ...]) -> MessageView:
    return MessageView(
        id=value.id,
        session_id=value.session_id,
        run_id=value.run_id,
        role=cast(MessageRole, value.role),
        content=value.content,
        citations=citations,
        created_at=value.created_at,
    )


class MessageHistory:
    """保存最终交互内容；运行步骤和流式事件仍由 agent 拥有。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    def append_user(
        self, session_id: str, user_id: str, run_id: str, content: str
    ) -> MessageView:
        return self._save(session_id, user_id, run_id, "user", content, ())

    def save_answer(
        self,
        session_id: str,
        user_id: str,
        run_id: str,
        content: str,
        citations: tuple[CitationInput, ...] = (),
    ) -> MessageView:
        return self._save(session_id, user_id, run_id, "assistant", content, citations)

    def _save(
        self,
        session_id: str,
        user_id: str,
        run_id: str,
        role: MessageRole,
        content: str,
        citations: tuple[CitationInput, ...],
    ) -> MessageView:
        clean_content = content.strip()
        if not clean_content:
            raise InvalidSessionInput("消息内容不能为空")
        normalized_citations: list[CitationInput] = []
        for item in citations:
            normalized = CitationInput(
                document_id=item.document_id.strip(),
                document_version_id=item.document_version_id.strip(),
                chunk_id=item.chunk_id.strip(),
                title_snapshot=item.title_snapshot.strip(),
                quote=item.quote.strip(),
                source_url=item.source_url,
            )
            if not all(
                (
                    normalized.document_id,
                    normalized.document_version_id,
                    normalized.chunk_id,
                    normalized.title_snapshot,
                    normalized.quote,
                )
            ):
                raise InvalidSessionInput(
                    "引用必须包含文档、版本、片段、标题和自包含摘录"
                )
            normalized_citations.append(normalized)
        with self._database.transaction() as db:
            owner = require_session(db, session_id, user_id)
            existing = db.scalar(
                select(Message).where(
                    Message.session_id == session_id,
                    Message.run_id == run_id,
                    Message.role == role,
                )
            )
            if existing is not None:
                saved = tuple(
                    _citation_view(value)
                    for value in db.scalars(
                        select(Citation)
                        .where(Citation.message_id == existing.id)
                        .order_by(Citation.position)
                    ).all()
                )
                expected = tuple(
                    (
                        value.document_id,
                        value.document_version_id,
                        value.chunk_id,
                        value.title_snapshot,
                        value.quote,
                        value.source_url,
                    )
                    for value in normalized_citations
                )
                actual = tuple(
                    (
                        value.document_id,
                        value.document_version_id,
                        value.chunk_id,
                        value.title_snapshot,
                        value.quote,
                        value.source_url,
                    )
                    for value in saved
                )
                if existing.content != clean_content or expected != actual:
                    raise IdempotencyConflict("相同 Run 的消息内容与已保存结果不一致")
                return _message_view(existing, saved)
            if owner.status == "deleting":
                raise SessionDeleting("会话正在删除，不能写入消息")
            if owner.active_run_id != run_id:
                raise IdempotencyConflict("当前 Run 未领取该会话")
            message = Message(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
                role=role,
                content=clean_content,
            )
            db.add(message)
            db.flush()
            values: list[Citation] = []
            for position, item in enumerate(normalized_citations):
                value = Citation(
                    id=str(uuid4()),
                    message_id=message.id,
                    user_id=user_id,
                    position=position,
                    document_id=item.document_id,
                    document_version_id=item.document_version_id,
                    chunk_id=item.chunk_id,
                    title_snapshot=item.title_snapshot,
                    source_url=item.source_url,
                    quote=item.quote,
                )
                db.add(value)
                values.append(value)
        return _message_view(message, tuple(_citation_view(value) for value in values))

    def list(self, session_id: str, user_id: str) -> tuple[MessageView, ...]:
        with self._database.session() as db:
            require_session(db, session_id, user_id)
            messages = db.scalars(
                select(Message)
                .where(Message.session_id == session_id, Message.user_id == user_id)
                .order_by(Message.created_at, Message.id)
            ).all()
            result = []
            for message in messages:
                citations = tuple(
                    _citation_view(value)
                    for value in db.scalars(
                        select(Citation)
                        .where(Citation.message_id == message.id)
                        .order_by(Citation.position)
                    ).all()
                )
                result.append(_message_view(message, citations))
            return tuple(result)

    def list_citations(
        self, session_id: str, message_id: str, user_id: str
    ) -> tuple[CitationView, ...]:
        with self._database.session() as db:
            message = db.scalar(
                select(Message).where(
                    Message.id == message_id,
                    Message.session_id == session_id,
                    Message.user_id == user_id,
                )
            )
            if message is None:
                raise MessageNotFound("消息不存在或无权访问")
            values = db.scalars(
                select(Citation)
                .where(Citation.message_id == message_id, Citation.user_id == user_id)
                .order_by(Citation.position)
            ).all()
            return tuple(_citation_view(value) for value in values)
