"""研究、对比、练习和用户反馈结果的 HTTP 边界。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from server.controller.sessions.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    PracticeResponse,
    TaskResultResponse,
)
from server.controller.sessions.shared import get_sessions, schema_of, session_error
from server.controller.users import require_identity
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{session_id}/results", response_model=list[TaskResultResponse])
def list_task_results(
    session_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[TaskResultResponse]:
    try:
        values = sessions.results.list_tasks(session_id, identity.user_id)
    except SessionsError as exc:
        raise session_error(exc) from exc
    return [schema_of(TaskResultResponse, value) for value in values]


@router.get("/{session_id}/practice", response_model=list[PracticeResponse])
def list_practice(
    session_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[PracticeResponse]:
    try:
        values = sessions.results.list_practice(session_id, identity.user_id)
    except SessionsError as exc:
        raise session_error(exc) from exc
    return [schema_of(PracticeResponse, value) for value in values]


@router.put("/{session_id}/feedback", response_model=FeedbackResponse)
def save_feedback(
    session_id: str,
    body: FeedbackRequest,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> FeedbackResponse:
    try:
        value = sessions.results.save_feedback(
            session_id,
            identity.user_id,
            body.target_type,
            body.target_id,
            body.rating,
            body.comment,
        )
    except SessionsError as exc:
        raise session_error(exc) from exc
    return schema_of(FeedbackResponse, value)


@router.get("/{session_id}/feedback", response_model=list[FeedbackResponse])
def list_feedback(
    session_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[FeedbackResponse]:
    try:
        values = sessions.results.list_feedback(session_id, identity.user_id)
    except SessionsError as exc:
        raise session_error(exc) from exc
    return [schema_of(FeedbackResponse, value) for value in values]
