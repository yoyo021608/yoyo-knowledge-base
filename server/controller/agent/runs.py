"""Run 状态、事件回放、取消和继续入口。"""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from server.agent.errors import AgentError
from server.agent.module import AgentModule
from server.controller.agent.coordination import cancel_and_release
from server.controller.agent.schemas import EventResponse, RunResponse
from server.controller.agent.shared import agent_error, get_agent, run_response
from server.controller.sessions.shared import get_sessions, session_error
from server.controller.users import require_identity
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api/agent/runs", tags=["agent"])


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    agent: Annotated[AgentModule, Depends(get_agent)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RunResponse:
    try:
        return run_response(agent.runs.get(run_id, identity.user_id))
    except AgentError as exc:
        raise agent_error(exc) from exc


@router.get("/{run_id}/events", response_model=list[EventResponse])
def read_events(
    run_id: str,
    agent: Annotated[AgentModule, Depends(get_agent)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EventResponse]:
    try:
        values = agent.runs.read_events(run_id, identity.user_id, after_seq, limit)
    except AgentError as exc:
        raise agent_error(exc) from exc
    return [EventResponse.model_validate(asdict(value)) for value in values]


@router.post("/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: str,
    agent: Annotated[AgentModule, Depends(get_agent)],
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RunResponse:
    try:
        cancel_and_release(agent, sessions, run_id, identity.user_id)
        return run_response(agent.runs.get(run_id, identity.user_id))
    except AgentError as exc:
        raise agent_error(exc) from exc
    except SessionsError as exc:
        raise session_error(exc) from exc


@router.post("/{run_id}/continue", response_model=RunResponse)
def continue_run(
    run_id: str,
    agent: Annotated[AgentModule, Depends(get_agent)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RunResponse:
    """恢复为 queued；客户端以原 request_id 重发问题后复用快照继续。"""
    try:
        agent.runs.continue_run(run_id, identity.user_id)
        return run_response(agent.runs.get(run_id, identity.user_id))
    except AgentError as exc:
        raise agent_error(exc) from exc
