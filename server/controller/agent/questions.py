"""Agent 提问 HTTP 入口；先返回 Run，再由后台执行可恢复任务。"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from server.agent.errors import AgentError
from server.agent.module import AgentModule
from server.controller.agent.coordination import (
    QuestionCommand,
    execute_prepared_in_background,
    prepare_question,
)
from server.controller.agent.schemas import QuestionRequest, RunResponse
from server.controller.agent.shared import agent_error, get_agent, run_response
from server.controller.sessions.shared import get_sessions, session_error
from server.controller.users import require_identity
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post(
    "/questions",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ask_question(
    body: QuestionRequest,
    background_tasks: BackgroundTasks,
    agent: Annotated[AgentModule, Depends(get_agent)],
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RunResponse:
    command = QuestionCommand(
        session_id=body.session_id,
        request_id=body.request_id,
        question=body.question,
        mode=body.mode,
        topic_id=body.topic_id,
        tag=body.tag,
        document_ids=tuple(body.document_ids),
        version_ids=tuple(body.version_ids),
        user_answer=body.user_answer,
    )
    try:
        prepared = prepare_question(agent, sessions, identity.user_id, command)
        if prepared.should_execute:
            background_tasks.add_task(
                execute_prepared_in_background,
                agent,
                sessions,
                identity.user_id,
                prepared.bundle.run.id,
            )
        return run_response(prepared.bundle)
    except AgentError as exc:
        raise agent_error(exc) from exc
    except SessionsError as exc:
        raise session_error(exc) from exc
