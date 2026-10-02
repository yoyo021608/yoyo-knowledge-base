"""sessions 接入层共用的依赖、转换和错误映射。"""

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from server.sessions.errors import SessionBusy, SessionNotFound, SessionsError
from server.sessions.module import SessionsModule


def get_sessions(request: Request) -> SessionsModule:
    """取得启动入口装配好的 sessions 公开能力。"""
    return request.app.state.sessions  # type: ignore[no-any-return]


def schema_of[SchemaT: BaseModel](schema: type[SchemaT], value: Any) -> SchemaT:
    """把不可变领域值转换为 HTTP 响应模型。"""
    return schema.model_validate(asdict(value))


def session_error(exc: SessionsError) -> HTTPException:
    """把预期领域错误转换为稳定的 HTTP 状态。"""
    if isinstance(exc, SessionNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, SessionBusy):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
