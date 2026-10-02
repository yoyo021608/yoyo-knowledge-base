"""sessions HTTP 边界使用的请求与响应结构。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    name: str = Field(default="新会话", min_length=1, max_length=120)


class SessionResponse(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    active_run_id: str | None
    created_at: datetime
    updated_at: datetime


class CitationRequest(BaseModel):
    document_id: str
    document_version_id: str
    chunk_id: str
    title_snapshot: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1)
    source_url: str | None = None


class CitationResponse(CitationRequest):
    id: str
    message_id: str


class MessageResponse(BaseModel):
    id: str
    session_id: str
    run_id: str
    role: str
    content: str
    citations: list[CitationResponse]
    created_at: datetime


class TaskResultResponse(BaseModel):
    id: str
    session_id: str
    run_id: str
    kind: str
    question: str
    status: str
    result_json: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class PracticeResponse(BaseModel):
    id: str
    session_id: str
    run_id: str
    question: str
    answer: str
    verdict: str
    explanation: str
    mastery_snapshot_json: str
    created_at: datetime


class FeedbackRequest(BaseModel):
    target_type: Literal["message", "citation", "practice"]
    target_id: str
    rating: Literal[-1, 1]
    comment: str = ""


class FeedbackResponse(BaseModel):
    id: str
    session_id: str
    target_type: str
    target_id: str
    rating: int
    comment: str
    created_at: datetime
