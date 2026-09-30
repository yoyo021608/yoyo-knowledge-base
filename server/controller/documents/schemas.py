"""documents HTTP 边界使用的请求与响应结构。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentImportRequest(BaseModel):
    """文本、Markdown 或已抓取网页内容的单条录入请求。"""

    title: str | None = Field(default=None, max_length=300)
    content: str | None = None
    source_type: Literal["note", "markdown", "web"] = "note"
    source_url: str | None = None
    source_title: str | None = Field(default=None, max_length=300)
    topic_id: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)


class FileImportRequest(BaseModel):
    """无需 multipart 依赖的 Base64 常见资料文件录入请求。"""

    name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=28_000_000)
    content_type: str = Field(default="text/plain", min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=300)
    topic_id: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)


class ImportResponse(BaseModel):
    document_id: str
    version_id: str
    index_status: str


class BatchImportRequest(BaseModel):
    """最多一百条同用户资料；用户身份不从条目正文读取。"""

    items: list[DocumentImportRequest] = Field(min_length=1, max_length=100)


class ImportItemResponse(BaseModel):
    id: str
    job_id: str
    input_index: int
    status: str
    document_id: str | None
    error_message: str | None


class ImportJobResponse(BaseModel):
    id: str
    user_id: str
    mode: str
    status: str
    total_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime


class BatchJobResponse(BaseModel):
    job: ImportJobResponse
    items: list[ImportItemResponse]


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    topic_id: str | None
    title: str
    status: str
    is_favorite: bool
    current_version: int
    current_version_id: str
    index_status: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class SourceResponse(BaseModel):
    version_id: str
    content: str
    source_type: str
    source_url: str | None
    title: str
    captured_at: datetime


class VersionResponse(BaseModel):
    id: str
    document_id: str
    version: int
    title_snapshot: str
    content_snapshot: str
    index_status: str
    index_error: str | None
    source: SourceResponse
    created_at: datetime


class DocumentDetailResponse(BaseModel):
    document: DocumentResponse
    version: VersionResponse


class DocumentUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    topic_id: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)
    source_url: str | None = None


class RefreshStatusResponse(BaseModel):
    document_id: str
    version_id: str
    status: str
    error_message: str | None
    updated_at: datetime


class SearchRequest(BaseModel):
    text: str = Field(min_length=1)
    mode: Literal["keyword", "full_text", "vector", "hybrid"] = "hybrid"
    topic_id: str | None = None
    tag: str | None = None
    limit: int = Field(default=8, ge=1, le=50)


class SearchHitResponse(BaseModel):
    document_id: str
    version_id: str
    title: str
    content_snippet: str
    chunk_id: str
    source_url: str | None
    score: float


class KnowledgePointResponse(BaseModel):
    id: str
    chunk_id: str
    position: int
    content: str
    entity_ids: list[str]


class KnowledgeEntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str


class KnowledgeRelationResponse(BaseModel):
    id: str
    point_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str


class DocumentKnowledgeResponse(BaseModel):
    document_id: str
    version_id: str
    points: list[KnowledgePointResponse]
    entities: list[KnowledgeEntityResponse]
    relations: list[KnowledgeRelationResponse]


class TopicRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class TopicResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class TagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class TagResponse(BaseModel):
    id: str
    user_id: str
    name: str
    created_at: datetime


class FavoriteRequest(BaseModel):
    favorite: bool


class RelationRequest(BaseModel):
    target_document_id: str
    relation_type: str = Field(min_length=1, max_length=60)


class RelationResponse(BaseModel):
    id: str
    user_id: str
    source_document_id: str
    target_document_id: str
    relation_type: str
    created_at: datetime
