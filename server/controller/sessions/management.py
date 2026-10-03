"""会话创建、列表、改名、Run 领取和两阶段删除的 HTTP 边界。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from server.agent.errors import AgentError
from server.agent.module import AgentModule
from server.controller.agent.shared import agent_error, get_agent
from server.controller.sessions.schemas import SessionRequest, SessionResponse
from server.controller.sessions.shared import get_sessions, schema_of, session_error
from server.controller.users import require_identity
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionRequest,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> SessionResponse:
    try:
        return schema_of(
            SessionResponse, sessions.management.create(identity.user_id, body.name)
        )
    except SessionsError as exc:
        raise session_error(exc) from exc


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[SessionResponse]:
    return [
        schema_of(SessionResponse, value)
        for value in sessions.management.list(identity.user_id)
    ]


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> SessionResponse:
    try:
        return schema_of(
            SessionResponse, sessions.management.get(session_id, identity.user_id)
        )
    except SessionsError as exc:
        raise session_error(exc) from exc


@router.patch("/{session_id}", response_model=SessionResponse)
def rename_session(
    session_id: str,
    body: SessionRequest,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> SessionResponse:
    try:
        return schema_of(
            SessionResponse,
            sessions.management.rename(session_id, identity.user_id, body.name),
        )
    except SessionsError as exc:
        raise session_error(exc) from exc


@router.post("/{session_id}/delete", status_code=status.HTTP_202_ACCEPTED)
def begin_delete(
    session_id: str,
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    try:
        sessions.management.begin_delete(session_id, identity.user_id)
    except SessionsError as exc:
        raise session_error(exc) from exc
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def finish_delete(
    session_id: str,
    agent: Annotated[AgentModule, Depends(get_agent)],
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    try:
        session = sessions.management.get(session_id, identity.user_id)
        agent.runs.purge_session_runs(session_id, identity.user_id)
        if session.active_run_id is not None:
            sessions.management.release_run(
                session_id, identity.user_id, session.active_run_id
            )
        sessions.management.delete(session_id, identity.user_id)
    except SessionsError as exc:
        raise session_error(exc) from exc
    except AgentError as exc:
        raise agent_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
