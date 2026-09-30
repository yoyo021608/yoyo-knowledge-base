"""documents controller 共用的依赖和错误转换。"""

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from server.documents.errors import (
    DocumentNotFound,
    DocumentsError,
    ImportJobNotFound,
    VersionNotFound,
)
from server.documents.module import DocumentsModule


def get_documents(request: Request) -> DocumentsModule:
    """从应用状态取得已经装配完成的 documents 能力。"""
    return request.app.state.documents  # type: ignore[no-any-return]


def schema_of[SchemaT: BaseModel](schema: type[SchemaT], value: Any) -> SchemaT:
    """把不可变领域值转换为 HTTP 响应模型。"""
    return schema.model_validate(asdict(value))


def document_error(exc: DocumentsError) -> HTTPException:
    """把 documents 预期错误稳定映射为 HTTP 状态。"""
    if isinstance(exc, (DocumentNotFound, VersionNotFound, ImportJobNotFound)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
