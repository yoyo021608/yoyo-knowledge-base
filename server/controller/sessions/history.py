"""用户消息、最终回答和引用回放的 HTTP 边界。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from server.controller.sessions.schemas import CitationResponse, MessageResponse
from server.controller.sessions.shared import get_sessions, schema_of, session_error
from server.controller.users import require_identity
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(
    session_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[MessageResponse]:
    try:
        values = sessions.history.list(session_id, identity.user_id)
    except SessionsError as exc:
        raise session_error(exc) from exc
    return [schema_of(MessageResponse, value) for value in values]


@router.get(
    "/{session_id}/messages/{message_id}/citations",
    response_model=list[CitationResponse],
)
def list_citations(
    session_id: str,
    message_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[CitationResponse]:
    try:
        values = sessions.history.list_citations(
            session_id, message_id, identity.user_id
        )
    except SessionsError as exc:
        raise session_error(exc) from exc
    return [schema_of(CitationResponse, value) for value in values]
