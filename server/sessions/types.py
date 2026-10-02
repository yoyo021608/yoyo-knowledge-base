"""sessions 对外使用且不依赖 FastAPI 或 ORM 的数据契约。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

SessionStatus = Literal["active", "deleting"]
MessageRole = Literal["user", "assistant"]
TaskStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ResultKind = Literal["research", "comparison"]
FeedbackTarget = Literal["message", "citation", "practice"]


@dataclass(frozen=True, slots=True)
class SessionView:
    """供列表、详情及协调流程读取的会话状态。"""

    id: str
    user_id: str
    name: str
    status: SessionStatus
    active_run_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CitationInput:
    """回答生成时交给 sessions 冻结的来源证据。"""

    document_id: str
    document_version_id: str
    chunk_id: str
    title_snapshot: str
    quote: str
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class CitationView:
    """脱离原文生命周期后仍可回放的引用快照。"""

    id: str
    message_id: str
    document_id: str
    document_version_id: str
    chunk_id: str
    title_snapshot: str
    quote: str
    source_url: str | None


@dataclass(frozen=True, slots=True)
class MessageView:
    """一条用户消息或最终回答及其引用。"""

    id: str
    session_id: str
    run_id: str
    role: MessageRole
    content: str
    citations: tuple[CitationView, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InteractionResultView:
    """研究和对比任务共用的可回放结果。"""

    id: str
    session_id: str
    run_id: str
    kind: ResultKind
    question: str
    status: TaskStatus
    result_json: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PracticeRecordView:
    """一次练习提交及当时的掌握度快照。"""

    id: str
    session_id: str
    run_id: str
    question: str
    answer: str
    verdict: str
    explanation: str
    mastery_snapshot_json: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FeedbackView:
    """用户对消息、引用或练习结果的评价。"""

    id: str
    session_id: str
    target_type: FeedbackTarget
    target_id: str
    rating: int
    comment: str
    created_at: datetime
