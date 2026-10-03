"""documents 模块对外传递且不依赖框架的数据类型。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

SourceType = Literal["note", "markdown", "web", "file"]
DocumentStatus = Literal["active", "archived"]
IndexStatus = Literal["queued", "processing", "ready", "failed"]
SearchMode = Literal["keyword", "full_text", "vector", "hybrid"]


@dataclass(frozen=True, slots=True)
class SingleImportInput:
    """单条资料录入所需数据；用户身份只能由可信入口注入。"""

    user_id: str
    title: str
    content: str
    source_type: SourceType = "note"
    source_url: str | None = None
    source_title: str | None = None
    topic_id: str | None = None
    tags: tuple[str, ...] = ()
    file_object_id: str | None = None


@dataclass(frozen=True, slots=True)
class ImportResult:
    """单条资料创建后返回的文档、版本和索引状态。"""

    document_id: str
    version_id: str
    index_status: IndexStatus


@dataclass(frozen=True, slots=True)
class BatchImportInput:
    """同一用户的一组录入条目。"""

    user_id: str
    items: tuple[SingleImportInput, ...]


@dataclass(frozen=True, slots=True)
class ImportJobView:
    """批量录入任务的聚合进度。"""

    id: str
    user_id: str
    mode: str
    status: str
    total_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ImportItemView:
    """批量任务中一条输入的处理结果。"""

    id: str
    job_id: str
    input_index: int
    status: str
    document_id: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class BatchJobResult:
    """任务进度及其逐条结果。"""

    job: ImportJobView
    items: tuple[ImportItemView, ...]


@dataclass(frozen=True, slots=True)
class DocumentFilter:
    """文档列表的可组合筛选条件。"""

    keyword: str | None = None
    topic_id: str | None = None
    tag: str | None = None
    source_type: SourceType | None = None
    index_status: IndexStatus | None = None
    status: DocumentStatus | None = "active"
    is_favorite: bool | None = None


@dataclass(frozen=True, slots=True)
class DocumentView:
    """文档列表和详情共用的当前状态。"""

    id: str
    user_id: str
    topic_id: str | None
    title: str
    status: DocumentStatus
    is_favorite: bool
    current_version: int
    current_version_id: str
    index_status: IndexStatus
    tags: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SourceSnapshotView:
    """随版本冻结的资料来源。"""

    version_id: str
    content: str
    source_type: SourceType
    source_url: str | None
    title: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentVersionView:
    """不可变的文档历史版本。"""

    id: str
    document_id: str
    version: int
    title_snapshot: str
    content_snapshot: str
    index_status: IndexStatus
    index_error: str | None
    source: SourceSnapshotView
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentDetail:
    """文档当前状态和当前版本正文。"""

    document: DocumentView
    version: DocumentVersionView


@dataclass(frozen=True, slots=True)
class DocumentUpdateInput:
    """编辑文档时创建新版本的数据。"""

    title: str
    content: str
    topic_id: str | None = None
    tags: tuple[str, ...] = ()
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class TopicInput:
    """专题名称和说明。"""

    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class TopicView:
    """当前用户拥有的专题。"""

    id: str
    user_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TagView:
    """当前用户拥有的标签。"""

    id: str
    user_id: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RelationInput:
    """两个同属当前用户的文档之间的有向关联。"""

    user_id: str
    source_document_id: str
    target_document_id: str
    relation_type: str


@dataclass(frozen=True, slots=True)
class DocumentRelationView:
    """文档之间的业务关联。"""

    id: str
    user_id: str
    source_document_id: str
    target_document_id: str
    relation_type: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    """唯一标识一次版本索引任务。"""

    document_id: str
    version_id: str


@dataclass(frozen=True, slots=True)
class RefreshStatusView:
    """指定文档当前版本的索引状态。"""

    document_id: str
    version_id: str
    status: IndexStatus
    error_message: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Agent 或用户发起的候选知识查询。"""

    user_id: str
    text: str
    mode: SearchMode = "hybrid"
    topic_id: str | None = None
    tag: str | None = None
    limit: int = 8
    document_ids: tuple[str, ...] = ()
    version_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchHit:
    """经归属和当前版本过滤后的候选片段。"""

    document_id: str
    version_id: str
    title: str
    content_snippet: str
    chunk_id: str
    source_url: str | None
    score: float


@dataclass(frozen=True, slots=True)
class KnowledgePointView:
    """能够定位回当前文档片段的知识点。"""

    id: str
    chunk_id: str
    position: int
    content: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeEntityView:
    """当前文档知识点明确提及的实体。"""

    id: str
    name: str
    entity_type: str


@dataclass(frozen=True, slots=True)
class KnowledgeRelationView:
    """两个实体在同一知识点中的可追溯联系。"""

    id: str
    point_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeView:
    """文档当前 ready 版本的知识结构。"""

    document_id: str
    version_id: str
    points: tuple[KnowledgePointView, ...]
    entities: tuple[KnowledgeEntityView, ...]
    relations: tuple[KnowledgeRelationView, ...]


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """当前用户的知识导出范围。"""

    user_id: str
    topic_id: str | None = None
    tag: str | None = None
    document_ids: tuple[str, ...] = ()
    format: Literal["markdown", "json"] = "markdown"


@dataclass(frozen=True, slots=True)
class ExportResult:
    """无需写临时文件即可由 HTTP 层下载的导出结果。"""

    file_name: str
    content: bytes
    media_type: str


@dataclass(frozen=True, slots=True)
class SourceInput:
    """模块内部保存来源快照所需数据。"""

    user_id: str
    document_id: str
    version_id: str
    content: str
    source_type: SourceType
    source_url: str | None
    title: str
    file_object_id: str | None = None


@dataclass(frozen=True, slots=True)
class StoredFileInput:
    """文件录入入口接收的原始文件和组织信息。"""

    user_id: str
    name: str
    content: bytes
    content_type: str
    title: str | None = None
    topic_id: str | None = None
    tags: tuple[str, ...] = ()
