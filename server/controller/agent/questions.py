"""Agent 提问 HTTP 入口；业务协调由无框架依赖的 coordination 完成。"""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from server.agent.errors import AgentError
from server.agent.module import AgentModule
from server.controller.agent.coordination import (
    QuestionCommand,
    QuestionOutcome,
    execute_question,
)
from server.controller.agent.schemas import (
    AnswerResponse,
    EvaluationResponse,
    QuestionRequest,
    QuestionResponse,
)
from server.controller.agent.shared import agent_error, get_agent
from server.controller.sessions.shared import get_sessions, session_error
from server.controller.users import require_identity
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _response(outcome: QuestionOutcome) -> QuestionResponse:
    return QuestionResponse(
        run_id=outcome.run_id,
        status=outcome.status,
        message_id=outcome.message.id if outcome.message is not None else None,
        answer=AnswerResponse.model_validate(asdict(outcome.output.answer)),
        evaluation=EvaluationResponse.model_validate(asdict(outcome.output.evaluation)),
        mode_result=outcome.output.mode_result,
    )


@router.post("/questions", response_model=QuestionResponse)
def ask_question(
    body: QuestionRequest,
    agent: Annotated[AgentModule, Depends(get_agent)],
    sessions: Annotated[SessionsModule, Depends(get_sessions)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> QuestionResponse:
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
        return _response(execute_question(agent, sessions, identity.user_id, command))
    except AgentError as exc:
        raise agent_error(exc) from exc
    except SessionsError as exc:
        raise session_error(exc) from exc
