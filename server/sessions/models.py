"""sessions 独占的持久化模型；引用只保存快照，不反向约束 documents。"""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ConversationSession(Base):
    """用户可管理的会话及当前活动 Run 关联。"""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    active_run_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Message(Base):
    """按 Run 和角色幂等保存的最终交互消息。"""

    __tablename__ = "session_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "run_id", "role", name="uq_session_messages_run_role"
        ),
        Index("ix_session_messages_order", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Citation(Base):
    """回答保存时冻结的证据定位和展示信息。"""

    __tablename__ = "session_citations"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "position", name="uq_session_citations_position"
        ),
        Index("ix_session_citations_message", "message_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("session_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # 以下标识故意不建外键；原文删除后历史回答仍能展示当时的证据快照。
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text, nullable=False)


class InteractionResult(Base):
    """研究报告和文档对比是相同生命周期下的两类交互结果。"""

    __tablename__ = "session_interaction_results"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "run_id", "kind", name="uq_session_results_run_kind"
        ),
        Index("ix_session_results_session", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PracticeRecord(Base):
    """学习练习的提交、判定和掌握度快照。"""

    __tablename__ = "session_practice_records"
    __table_args__ = (
        UniqueConstraint("session_id", "run_id", name="uq_session_practice_run"),
        Index("ix_session_practice_session", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    mastery_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Feedback(Base):
    """对指定交互结果的用户反馈，同一目标可覆盖更新。"""

    __tablename__ = "session_feedback"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_session_feedback_target"
        ),
        Index("ix_session_feedback_session", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
