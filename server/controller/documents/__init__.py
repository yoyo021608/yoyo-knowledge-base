"""documents 的全部 HTTP 子入口在这里统一装配。"""

from fastapi import APIRouter

from server.controller.documents.imports import router as imports_router
from server.controller.documents.lifecycle import router as lifecycle_router
from server.controller.documents.organization import router as organization_router
from server.controller.documents.query import router as query_router
from server.controller.documents.shared import get_documents

router = APIRouter()
router.include_router(lifecycle_router)
router.include_router(imports_router)
router.include_router(query_router)
router.include_router(organization_router)

__all__ = ["get_documents", "router"]
