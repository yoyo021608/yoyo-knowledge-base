"""documents 领域独占的持久化模型。"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from server.infra.database import Base


def utc_now() -> datetime:
    """返回带时区的当前时间，供文档持久化默认值使用。"""
    return datetime.now(UTC)


class VectorType(UserDefinedType[str]):
    """让 ORM 使用 PostgreSQL pgvector，同时保持 SQLite 测试可建表。"""

    cache_ok = True

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kwargs: object) -> str:
        return f"vector({self.dimensions})"


class Topic(Base):
    """用户创建的专题；删除专题只解除文档归类。"""

    __tablename__ = "document_topics"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_document_topics_user_name"),
        Index("ix_document_topics_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Tag(Base):
    """用户创建的标签；标签名在用户范围内唯一。"""

    __tablename__ = "document_tags"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_document_tags_user_name"),
        Index("ix_document_tags_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Document(Base):
    """文档当前状态；正文始终保存在不可变版本中。"""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_status", "user_id", "status"),
        Index("ix_documents_user_topic", "user_id", "topic_id"),
        Index("ix_documents_current_version", "current_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_topics.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 避免建表时形成循环外键；业务层同时校验当前版本确实属于该文档。
    current_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    index_status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class DocumentVersion(Base):
    """文档的一份只读历史快照。"""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_versions_number"),
        Index("ix_document_versions_document", "document_id", "version"),
        Index("ix_document_versions_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False
    )
    index_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    index_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class SourceSnapshot(Base):
    """随版本冻结的来源正文和来源定位信息。"""

    __tablename__ = "document_source_snapshots"
    __table_args__ = (Index("ix_document_sources_document", "document_id"),)

    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    file_object_id: Mapped[str | None] = mapped_column(String(36))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DocumentTag(Base):
    """文档和标签的用户内多对多关系。"""

    __tablename__ = "document_tag_links"
    __table_args__ = (Index("ix_document_tag_links_tag", "tag_id"),)

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class DocumentRelation(Base):
    """两个文档之间可解释的业务关联。"""

    __tablename__ = "document_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relation_type",
            name="uq_document_relations_edge",
        ),
        Index("ix_document_relations_user_source", "user_id", "source_document_id"),
        Index("ix_document_relations_user_target", "user_id", "target_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    target_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DocumentChunk(Base):
    """绑定用户和版本的可定位检索片段。"""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "position", name="uq_document_chunks_position"),
        Index("ix_document_chunks_lookup", "user_id", "document_id", "version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 当前实现保存可重复计算的稀疏词频向量；可由 infra 的向量引擎适配器替换。
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    # PostgreSQL 使用该列执行 pgvector 近邻计算；字符串是 pgvector 接受的字面量。
    embedding: Mapped[str] = mapped_column(VectorType(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DocumentIndexTask(Base):
    """与版本同事务保存的持久化索引任务，供失败重试和定期扫描。"""

    __tablename__ = "document_index_tasks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_id", name="uq_document_index_tasks_version"
        ),
        Index("ix_document_index_tasks_status", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class KnowledgePoint(Base):
    """从片段中抽取且能回到原文位置的概念或结论。"""

    __tablename__ = "document_knowledge_points"
    __table_args__ = (
        UniqueConstraint("version_id", "position", name="uq_knowledge_points_position"),
        Index(
            "ix_knowledge_points_source",
            "user_id",
            "document_id",
            "version_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class KnowledgeEntity(Base):
    """用户知识库中可跨文档复用的显式人物、项目或技术词。"""

    __tablename__ = "document_knowledge_entities"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "normalized_name", name="uq_knowledge_entities_user_name"
        ),
        Index("ix_knowledge_entities_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class KnowledgePointEntity(Base):
    """知识点对实体的可追溯提及关系。"""

    __tablename__ = "document_knowledge_point_entities"
    __table_args__ = (
        Index(
            "ix_knowledge_point_entities_source",
            "user_id",
            "document_id",
            "version_id",
        ),
    )

    point_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_knowledge_points.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_knowledge_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )


class KnowledgeRelation(Base):
    """同一知识点中两个显式实体的共现关系及其证据位置。"""

    __tablename__ = "document_knowledge_relations"
    __table_args__ = (
        UniqueConstraint(
            "point_id",
            "source_entity_id",
            "target_entity_id",
            name="uq_knowledge_relations_evidence",
        ),
        Index(
            "ix_knowledge_relations_source",
            "user_id",
            "document_id",
            "version_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    point_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(
        String(40), default="co_occurs", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ImportJob(Base):
    """批量录入任务的聚合状态。"""

    __tablename__ = "document_import_jobs"
    __table_args__ = (Index("ix_document_import_jobs_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), default="batch", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class ImportItem(Base):
    """批量任务中一条输入及其幂等处理结果。"""

    __tablename__ = "document_import_items"
    __table_args__ = (
        UniqueConstraint("job_id", "input_index", name="uq_import_items_job_index"),
        Index("ix_document_import_items_job", "job_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    input_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(36))
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
