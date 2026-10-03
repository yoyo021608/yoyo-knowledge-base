"""Agent 接入层共用依赖、响应转换和错误映射。"""

from fastapi import HTTPException, Request, status

from server.agent.errors import (
    AgentError,
    AgentRunConflict,
    AgentRunNotFound,
    FinalizationInProgress,
    RetrievalUnavailable,
    SnapshotConflict,
)
from server.agent.module import AgentModule
from server.agent.types import RunBundle
from server.controller.agent.schemas import RunResponse


def get_agent(request: Request) -> AgentModule:
    return request.app.state.agent  # type: ignore[no-any-return]


def run_response(bundle: RunBundle) -> RunResponse:
    run = bundle.run
    return RunResponse(
        id=run.id,
        session_id=run.session_id,
        request_id=run.request_id,
        mode=run.mode,
        status=run.status,
        last_event_seq=run.last_event_seq,
        failure_reason=run.failure_reason,
        step=bundle.snapshot.step,
        revision=bundle.snapshot.revision,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def agent_error(exc: AgentError) -> HTTPException:
    if isinstance(exc, AgentRunNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (AgentRunConflict, SnapshotConflict, FinalizationInProgress)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, RetrievalUnavailable):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
