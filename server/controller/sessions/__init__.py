"""sessions 的 HTTP 子入口统一装配。"""

from fastapi import APIRouter

from server.controller.sessions.history import router as history_router
from server.controller.sessions.management import router as management_router
from server.controller.sessions.results import router as results_router
from server.controller.sessions.shared import get_sessions

router = APIRouter()
router.include_router(management_router)
router.include_router(history_router)
router.include_router(results_router)

__all__ = ["get_sessions", "router"]
