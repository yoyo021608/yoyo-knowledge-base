"""文档维护、版本、来源和索引状态的 HTTP 边界。"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from server.controller.documents.schemas import (
    DocumentDetailResponse,
    DocumentKnowledgeResponse,
    DocumentResponse,
    DocumentUpdateRequest,
    RefreshStatusResponse,
    SourceResponse,
    VersionResponse,
)
from server.controller.documents.shared import document_error, get_documents, schema_of
from server.controller.users import require_identity
from server.documents.errors import DocumentsError
from server.documents.module import DocumentsModule
from server.documents.types import DocumentFilter, DocumentUpdateInput, RefreshRequest
from server.users.types import IdentityContext

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
    keyword: str | None = None,
    topic_id: str | None = None,
    tag: str | None = None,
    source_type: Literal["note", "markdown", "web", "file"] | None = None,
    index_status: Literal["queued", "processing", "ready", "failed"] | None = None,
    document_status: Annotated[
        Literal["active", "archived"] | None, Query(alias="status")
    ] = "active",
    is_favorite: bool | None = None,
) -> list[DocumentResponse]:
    """按可组合条件列出当前用户文档。"""
    values = documents.editor.list(
        identity.user_id,
        DocumentFilter(
            keyword=keyword,
            topic_id=topic_id,
            tag=tag,
            source_type=source_type,
            index_status=index_status,
            status=document_status,
            is_favorite=is_favorite,
        ),
    )
    return [schema_of(DocumentResponse, value) for value in values]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> DocumentDetailResponse:
    """读取当前文档和当前版本正文。"""
    try:
        detail = documents.editor.get(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(DocumentDetailResponse, detail)


@router.put("/documents/{document_id}", response_model=VersionResponse)
def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> VersionResponse:
    """创建新版本并刷新索引，旧版本保持只读。"""
    try:
        version = documents.editor.update(
            document_id,
            identity.user_id,
            DocumentUpdateInput(
                title=body.title,
                content=body.content,
                topic_id=body.topic_id,
                tags=tuple(body.tags),
                source_url=body.source_url,
            ),
        )
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(VersionResponse, version)


@router.get("/documents/{document_id}/versions", response_model=list[VersionResponse])
def list_versions(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[VersionResponse]:
    """按新到旧查看文档版本。"""
    try:
        values = documents.editor.list_versions(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return [schema_of(VersionResponse, value) for value in values]


@router.get(
    "/documents/{document_id}/versions/{version_id}", response_model=VersionResponse
)
def get_version(
    document_id: str,
    version_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> VersionResponse:
    """读取回答引用所绑定的具体历史版本。"""
    try:
        value = documents.editor.get_version(document_id, version_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(VersionResponse, value)


@router.get("/documents/{document_id}/source", response_model=SourceResponse)
def get_source(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> SourceResponse:
    """查看当前版本来源地址和导入时快照。"""
    try:
        value = documents.sources.get(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(SourceResponse, value)


@router.get(
    "/documents/{document_id}/knowledge",
    response_model=DocumentKnowledgeResponse,
)
def get_document_knowledge(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> DocumentKnowledgeResponse:
    """读取当前版本已生成的知识点、实体和可追溯关系。"""
    try:
        value = documents.knowledge.get(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(DocumentKnowledgeResponse, value)


@router.get("/documents/{document_id}/index", response_model=RefreshStatusResponse)
def get_index_status(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RefreshStatusResponse:
    """查看文档当前版本索引状态。"""
    try:
        value = documents.indexer.get_status(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(RefreshStatusResponse, value)


@router.post(
    "/documents/{document_id}/index/retry", response_model=RefreshStatusResponse
)
def retry_index(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RefreshStatusResponse:
    """按当前版本标识幂等重试索引，不创建重复文档。"""
    try:
        current = documents.indexer.get_status(document_id, identity.user_id)
        documents.indexer.refresh(
            RefreshRequest(document_id=document_id, version_id=current.version_id)
        )
        refreshed = documents.indexer.get_status(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(RefreshStatusResponse, refreshed)


@router.post("/documents/{document_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_document(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """归档文档并立即停止默认展示和检索。"""
    try:
        documents.editor.archive(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_document(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """恢复已归档文档。"""
    try:
        documents.editor.restore(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """清除当前用户文档的正文、历史版本、索引和组织关系。"""
    try:
        documents.editor.delete(document_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
