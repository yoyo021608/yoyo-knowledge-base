"""Agent 模块公开的数据契约；不依赖 FastAPI、ORM 或其他业务模块。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

AgentMode = Literal["quick", "research", "comparison", "study"]
RunStatus = Literal[
    "queued", "running", "paused", "finalizing", "cancelled", "completed", "failed"
]
RunStep = Literal["rewrite", "retrieve", "generate", "persist_answer"]
SearchMode = Literal["keyword", "full_text", "vector", "hybrid"]
EvidenceStatus = Literal["sufficient", "insufficient", "failed"]


@dataclass(frozen=True, slots=True)
class MessageContext:
    """供模型读取的历史消息，不承担 sessions 消息持久化。"""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class SearchHitContext:
    """经 documents 校验后交给 Agent 使用的证据片段。"""

    document_id: str
    version_id: str
    title: str
    content_snippet: str
    chunk_id: str
    source_url: str | None
    score: float


@dataclass(frozen=True, slots=True)
class ContextBudget:
    model_window: int
    reserved_output_tokens: int
    safety_margin: int
    history_budget: int
    evidence_budget: int


@dataclass(frozen=True, slots=True)
class ContextInput:
    question: str
    history: tuple[MessageContext, ...]
    search_hits: tuple[SearchHitContext, ...]
    budget: ContextBudget


@dataclass(frozen=True, slots=True)
class ContextPacket:
    system_prompt: str
    messages: tuple[MessageContext, ...]
    sources: tuple[SearchHitContext, ...]
    input_tokens: int


@dataclass(frozen=True, slots=True)
class RewriteInput:
    question: str
    history: tuple[MessageContext, ...]


@dataclass(frozen=True, slots=True)
class RewrittenQuestion:
    text: str
    keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    query: str
    mode: SearchMode
    limit: int
    topic_id: str | None = None
    tag: str | None = None
    document_ids: tuple[str, ...] = ()
    version_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    permission: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    success: bool
    data: str
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    sufficient: bool
    reason: str
    hit_count: int
    missing_information: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NextRetrieval:
    retry: bool
    query: str


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    document_id: str
    document_version_id: str
    chunk_id: str
    title_snapshot: str
    source_url: str | None
    quote: str


@dataclass(frozen=True, slots=True)
class AnswerResult:
    text: str
    citations: tuple[AnswerCitation, ...]
    evidence_status: EvidenceStatus


@dataclass(frozen=True, slots=True)
class RunEvaluation:
    hit_count: int
    citation_coverage: float
    evidence_status: EvidenceStatus
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class WorkflowOutput:
    """Agent 交给 controller 的完整结果；保存位置仍由 sessions 决定。"""

    answer: AnswerResult
    evaluation: RunEvaluation
    mode_result: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ExecutionOptions:
    """不同模式共用的范围参数，不包含可信用户身份。"""

    topic_id: str | None = None
    tag: str | None = None
    document_ids: tuple[str, ...] = ()
    version_ids: tuple[str, ...] = ()
    user_answer: str | None = None


@dataclass(frozen=True, slots=True)
class Run:
    id: str
    session_id: str
    user_id: str
    request_id: str
    mode: AgentMode
    status: RunStatus
    last_event_seq: int
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RunEvent:
    id: str
    run_id: str
    event_seq: int
    event_type: str
    payload: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    run_id: str
    input_message_id: str | None
    input: ContextInput
    step: RunStep
    queries: tuple[str, ...]
    selected_sources: tuple[SearchHitContext, ...]
    result: AnswerResult | None
    mode_result: dict[str, object] | None
    chat_model: str
    attempt: int
    revision: int
    # 恢复执行必须使用最初的检索范围，不能依赖浏览器重新提交参数。
    options: ExecutionOptions = ExecutionOptions()


@dataclass(frozen=True, slots=True)
class RunBundle:
    run: Run
    snapshot: RunSnapshot
