"""知识候选检索和资料导出的 HTTP 边界。"""

from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response

from server.controller.documents.schemas import SearchHitResponse, SearchRequest
from server.controller.documents.shared import document_error, get_documents, schema_of
from server.controller.users import require_identity
from server.documents.errors import DocumentsError
from server.documents.module import DocumentsModule
from server.documents.types import ExportRequest, SearchQuery
from server.users.types import IdentityContext

router = APIRouter(prefix="/api", tags=["document-query"])


@router.post("/documents/search", response_model=list[SearchHitResponse])
def search_documents(
    body: SearchRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[SearchHitResponse]:
    """返回候选片段，不在 controller 中执行回答或证据判断。"""
    try:
        hits = documents.search.search(
            SearchQuery(
                user_id=identity.user_id,
                text=body.text,
                mode=body.mode,
                topic_id=body.topic_id,
                tag=body.tag,
                limit=body.limit,
            )
        )
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return [schema_of(SearchHitResponse, hit) for hit in hits]


@router.get("/documents/export")
def export_documents(
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
    export_format: Annotated[
        Literal["markdown", "json"], Query(alias="format")
    ] = "markdown",
    topic_id: str | None = None,
    tag: str | None = None,
    document_id: Annotated[list[str] | None, Query()] = None,
) -> Response:
    """下载当前用户筛选范围内的文档和来源。"""
    try:
        result = documents.exporter.export(
            ExportRequest(
                user_id=identity.user_id,
                topic_id=topic_id,
                tag=tag,
                document_ids=tuple(document_id or ()),
                format=export_format,
            )
        )
    except DocumentsError as exc:
        raise document_error(exc) from exc
    encoded_name = quote(result.file_name)
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )
