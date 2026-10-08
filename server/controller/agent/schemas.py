"""Agent HTTP 边界的请求和响应结构。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QuestionRequest(BaseModel):
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=20_000)
    mode: Literal["quick", "research", "comparison", "study"] = "quick"
    topic_id: str | None = None
    tag: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    version_ids: list[str] = Field(default_factory=list, max_length=20)
    user_answer: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def validate_mode_scope(self) -> "QuestionRequest":
        if (
            self.mode == "comparison"
            and len(self.document_ids) + len(self.version_ids) < 2
        ):
            raise ValueError("文档对比至少需要两个文档或版本")
        if self.user_answer is not None and self.mode != "study":
            raise ValueError("user_answer 只用于学习模式")
        return self


class RunResponse(BaseModel):
    id: str
    session_id: str
    request_id: str
    mode: str
    status: str
    last_event_seq: int
    failure_reason: str | None
    step: str
    revision: int
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    id: str
    run_id: str
    event_seq: int
    event_type: str
    payload: str
    created_at: datetime
