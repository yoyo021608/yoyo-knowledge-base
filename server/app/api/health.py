from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """健康检查：只证明服务已经启动。"""
    return {"status": "ok"}
