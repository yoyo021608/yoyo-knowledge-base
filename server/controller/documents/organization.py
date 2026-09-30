"""专题、标签、收藏和文档关联的 HTTP 边界。"""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from server.controller.documents.schemas import (
    FavoriteRequest,
    RelationRequest,
    RelationResponse,
    TagRequest,
    TagResponse,
    TopicRequest,
    TopicResponse,
)
from server.controller.documents.shared import get_documents
from server.controller.users import require_identity
from server.documents.errors import (
    DocumentNotFound,
    DocumentsError,
    DuplicateName,
    RelationNotFound,
    TagNotFound,
    TopicNotFound,
)
from server.documents.module import DocumentsModule
from server.documents.types import RelationInput, TopicInput
from server.users.types import IdentityContext

router = APIRouter(prefix="/api", tags=["document-organization"])


def _schema[SchemaT: BaseModel](schema: type[SchemaT], value: Any) -> SchemaT:
    return schema.model_validate(asdict(value))


def _organization_error(exc: DocumentsError) -> HTTPException:
    if isinstance(
        exc,
        (DocumentNotFound, TopicNotFound, TagNotFound, RelationNotFound),
    ):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateName):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED
)
def create_topic(
    body: TopicRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> TopicResponse:
    """创建当前用户的专题。"""
    try:
        value = documents.organization.create_topic(
            identity.user_id, TopicInput(name=body.name, description=body.description)
        )
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return _schema(TopicResponse, value)


@router.get("/topics", response_model=list[TopicResponse])
def list_topics(
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[TopicResponse]:
    """列出当前用户专题。"""
    return [
        _schema(TopicResponse, value)
        for value in documents.organization.list_topics(identity.user_id)
    ]


@router.put("/topics/{topic_id}", response_model=TopicResponse)
def update_topic(
    topic_id: str,
    body: TopicRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> TopicResponse:
    """修改专题名称和说明。"""
    try:
        value = documents.organization.update_topic(
            identity.user_id,
            topic_id,
            TopicInput(name=body.name, description=body.description),
        )
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return _schema(TopicResponse, value)


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(
    topic_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """删除专题并解除文档归类。"""
    try:
        documents.organization.delete_topic(identity.user_id, topic_id)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    body: TagRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> TagResponse:
    """创建当前用户标签。"""
    try:
        value = documents.organization.create_tag(identity.user_id, body.name)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return _schema(TagResponse, value)


@router.get("/tags", response_model=list[TagResponse])
def list_tags(
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[TagResponse]:
    """列出当前用户标签。"""
    return [
        _schema(TagResponse, value)
        for value in documents.organization.list_tags(identity.user_id)
    ]


@router.put("/tags/{tag_id}", response_model=TagResponse)
def rename_tag(
    tag_id: str,
    body: TagRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> TagResponse:
    """重命名标签且保留文档标记。"""
    try:
        value = documents.organization.rename_tag(identity.user_id, tag_id, body.name)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return _schema(TagResponse, value)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """删除标签并解除全部文档标记。"""
    try:
        documents.organization.delete_tag(identity.user_id, tag_id)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/documents/{document_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def attach_tag(
    document_id: str,
    tag_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """给文档附加一个已有标签。"""
    try:
        documents.organization.attach_tag(document_id, tag_id, identity.user_id)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/documents/{document_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag(
    document_id: str,
    tag_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """取消文档上的一个标签。"""
    try:
        documents.organization.detach_tag(document_id, tag_id, identity.user_id)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/documents/{document_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def set_favorite(
    document_id: str,
    body: FavoriteRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """设置或取消文档收藏。"""
    try:
        documents.organization.set_favorite(
            document_id, identity.user_id, body.favorite
        )
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/documents/{document_id}/relations",
    response_model=RelationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(
    document_id: str,
    body: RelationRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> RelationResponse:
    """建立当前文档到另一个文档的有向关联。"""
    try:
        value = documents.organization.create_relation(
            RelationInput(
                user_id=identity.user_id,
                source_document_id=document_id,
                target_document_id=body.target_document_id,
                relation_type=body.relation_type,
            )
        )
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return _schema(RelationResponse, value)


@router.get("/documents/{document_id}/relations", response_model=list[RelationResponse])
def list_relations(
    document_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> list[RelationResponse]:
    """查看与指定文档相连的关系。"""
    try:
        values = documents.organization.list_relations(document_id, identity.user_id)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return [_schema(RelationResponse, value) for value in values]


@router.delete(
    "/document-relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_relation(
    relation_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """解除当前用户拥有的文档关联。"""
    try:
        documents.organization.delete_relation(relation_id, identity.user_id)
    except DocumentsError as exc:
        raise _organization_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
