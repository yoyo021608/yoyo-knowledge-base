"""Agent HTTP 子入口统一装配。"""

from fastapi import APIRouter

from server.controller.agent.questions import router as questions_router
from server.controller.agent.runs import router as runs_router
from server.controller.agent.shared import get_agent

router = APIRouter()
router.include_router(questions_router)
router.include_router(runs_router)

__all__ = ["get_agent", "router"]
