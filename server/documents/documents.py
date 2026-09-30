"""文档当前状态、历史版本和编辑操作。

本文件维护 Document 与 DocumentVersion 的一致性。编辑始终创建新版本，绝不覆盖
历史正文；组织信息和检索算法分别由 organization.py 与 search.py 负责。
"""

from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from server.documents.errors import (
    DocumentNotFound,
    InvalidDocumentInput,
    TopicNotFound,
    VersionNotFound,
)
from server.documents.indexing import DocumentIndexer
from server.documents.models import (
    Document,
    DocumentChunk,
    DocumentIndexTask,
    DocumentRelation,
    DocumentTag,
    DocumentVersion,
    ImportItem,
    KnowledgeEntity,
    KnowledgePoint,
    KnowledgePointEntity,
    KnowledgeRelation,
    SourceSnapshot,
    Tag,
    Topic,
)
from server.documents.sources import SourceManager, source_view
from server.documents.types import (
    DocumentDetail,
    DocumentFilter,
    DocumentStatus,
    DocumentUpdateInput,
    DocumentVersionView,
    DocumentView,
    IndexStatus,
    RefreshRequest,
    SourceInput,
    SourceType,
)
from server.infra.database import Database
from server.infra.files import LocalFileStorage


def clean_title(value: str) -> str:
    """统一标题空白并限制持久化长度。"""
    title = " ".join(value.split()).strip()
    if not title:
        raise InvalidDocumentInput("文档标题不能为空")
    if len(title) > 300:
        raise InvalidDocumentInput("文档标题不能超过 300 个字符")
    return title


def clean_content(value: str) -> str:
    """保留正文内部格式，只去除两端空白并拒绝空内容。"""
    content = value.strip()
    if not content:
        raise InvalidDocumentInput("文档正文不能为空")
    return content


def require_topic(session: Session, topic_id: str | None, user_id: str) -> None:
    """确保专题属于当前用户；空专题表示未归类。"""
    if topic_id is None:
        return
    topic = session.scalar(
        select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
    )
    if topic is None:
        raise TopicNotFound("专题不存在")


def require_document(session: Session, document_id: str, user_id: str) -> Document:
    """按用户归属读取文档，避免通过标识枚举其他用户资料。"""
    document = session.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    if document is None:
        raise DocumentNotFound("文档不存在")
    return document


def set_document_tags(
    session: Session, document_id: str, user_id: str, tag_names: tuple[str, ...]
) -> None:
    """用规范化标签名替换文档标签；不存在的标签在用户范围内创建。"""
    normalized = tuple(
        dict.fromkeys(
            " ".join(name.split()).strip() for name in tag_names if name.strip()
        )
    )
    if any(len(name) > 60 for name in normalized):
        raise InvalidDocumentInput("标签名不能超过 60 个字符")
    session.execute(delete(DocumentTag).where(DocumentTag.document_id == document_id))
    for name in normalized:
        tag = session.scalar(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        )
        if tag is None:
            tag = Tag(id=str(uuid4()), user_id=user_id, name=name)
            session.add(tag)
            session.flush()
        session.add(
            DocumentTag(document_id=document_id, tag_id=tag.id, user_id=user_id)
        )


def document_view(session: Session, document: Document) -> DocumentView:
    """生成不会泄露 ORM 对象的文档公开视图。"""
    tags = tuple(
        session.scalars(
            select(Tag.name)
            .join(DocumentTag, DocumentTag.tag_id == Tag.id)
            .where(
                DocumentTag.document_id == document.id,
                DocumentTag.user_id == document.user_id,
            )
            .order_by(Tag.name)
        ).all()
    )
    return DocumentView(
        id=document.id,
        user_id=document.user_id,
        topic_id=document.topic_id,
        title=document.title,
        status=cast(DocumentStatus, document.status),
        is_favorite=document.is_favorite,
        current_version=document.current_version,
        current_version_id=document.current_version_id,
        index_status=cast(IndexStatus, document.index_status),
        tags=tags,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def version_view(
    version: DocumentVersion, source: SourceSnapshot
) -> DocumentVersionView:
    """组合版本正文与同版本来源快照。"""
    return DocumentVersionView(
        id=version.id,
        document_id=version.document_id,
        version=version.version,
        title_snapshot=version.title_snapshot,
        content_snapshot=version.content_snapshot,
        index_status=cast(IndexStatus, version.index_status),
        index_error=version.index_error,
        source=source_view(source),
        created_at=version.created_at,
    )


class DocumentEditor:
    """读取和改变文档生命周期，并将新版本交给索引器刷新。"""

    def __init__(
        self,
        database: Database,
        indexer: DocumentIndexer,
        file_storage: LocalFileStorage | None = None,
    ) -> None:
        self._database = database
        self._indexer = indexer
        self._file_storage = file_storage

    def get(self, document_id: str, user_id: str) -> DocumentDetail:
        """读取文档当前状态、当前版本正文和来源。"""
        with self._database.session() as session:
            document = require_document(session, document_id, user_id)
            version = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == document.current_version_id,
                    DocumentVersion.document_id == document.id,
                )
            )
            source = session.get(SourceSnapshot, document.current_version_id)
            if version is None or source is None:
                raise VersionNotFound("文档当前版本不完整")
            return DocumentDetail(
                document=document_view(session, document),
                version=version_view(version, source),
            )

    def list(self, user_id: str, filters: DocumentFilter) -> tuple[DocumentView, ...]:
        """按归属和组合条件列出文档，默认排除已归档内容。"""
        with self._database.session() as session:
            statement = select(Document).where(Document.user_id == user_id)
            if filters.status is not None:
                statement = statement.where(Document.status == filters.status)
            if filters.topic_id is not None:
                statement = statement.where(Document.topic_id == filters.topic_id)
            if filters.index_status is not None:
                statement = statement.where(
                    Document.index_status == filters.index_status
                )
            if filters.is_favorite is not None:
                statement = statement.where(
                    Document.is_favorite.is_(filters.is_favorite)
                )
            if filters.keyword:
                keyword = f"%{filters.keyword.strip()}%"
                statement = statement.join(
                    DocumentVersion,
                    DocumentVersion.id == Document.current_version_id,
                ).where(
                    or_(
                        Document.title.ilike(keyword),
                        DocumentVersion.content_snapshot.ilike(keyword),
                    )
                )
            if filters.source_type is not None:
                statement = statement.join(
                    SourceSnapshot,
                    SourceSnapshot.version_id == Document.current_version_id,
                ).where(SourceSnapshot.source_type == filters.source_type)
            if filters.tag:
                statement = (
                    statement.join(DocumentTag, DocumentTag.document_id == Document.id)
                    .join(Tag, Tag.id == DocumentTag.tag_id)
                    .where(Tag.user_id == user_id, Tag.name == filters.tag.strip())
                )
            documents = session.scalars(
                statement.distinct().order_by(Document.updated_at.desc())
            ).all()
            return tuple(document_view(session, document) for document in documents)

    def update(
        self,
        document_id: str,
        user_id: str,
        update_input: DocumentUpdateInput,
    ) -> DocumentVersionView:
        """原子创建新版本和 queued 状态，再刷新新版本索引。"""
        title = clean_title(update_input.title)
        content = clean_content(update_input.content)
        with self._database.transaction() as session:
            document = require_document(session, document_id, user_id)
            require_topic(session, update_input.topic_id, user_id)
            previous_source = session.get(SourceSnapshot, document.current_version_id)
            if previous_source is None:
                raise VersionNotFound("文档当前来源不存在")
            next_source_url = (
                update_input.source_url
                if update_input.source_url is not None
                else previous_source.source_url
            )
            if previous_source.source_type == "web":
                parsed = urlparse(next_source_url or "")
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise InvalidDocumentInput(
                        "网页资料必须保留有效的 HTTP(S) 来源地址"
                    )
            version_id = str(uuid4())
            now = datetime.now(UTC)
            version = DocumentVersion(
                id=version_id,
                document_id=document.id,
                user_id=user_id,
                version=document.current_version + 1,
                title_snapshot=title,
                content_snapshot=content,
                index_status="queued",
                index_updated_at=now,
            )
            session.add(version)
            # 新版本必须先存在，随后同一事务内才能写来源快照与索引任务。
            session.flush()
            DocumentIndexer.queue_in_transaction(
                session, document.id, version_id, user_id
            )
            SourceManager.capture_in_transaction(
                session,
                SourceInput(
                    user_id=user_id,
                    document_id=document.id,
                    version_id=version_id,
                    content=content,
                    source_type=cast(SourceType, previous_source.source_type),
                    source_url=next_source_url,
                    title=title,
                    file_object_id=previous_source.file_object_id,
                ),
            )
            document.title = title
            document.topic_id = update_input.topic_id
            document.current_version += 1
            document.current_version_id = version_id
            document.index_status = "queued"
            document.updated_at = now
            set_document_tags(session, document.id, user_id, update_input.tags)

        self._indexer.refresh(
            RefreshRequest(document_id=document_id, version_id=version_id)
        )
        return self.get_version(document_id, version_id, user_id)

    def get_version(
        self, document_id: str, version_id: str, user_id: str
    ) -> DocumentVersionView:
        """校验文档归属后读取一个历史版本及其来源。"""
        with self._database.session() as session:
            require_document(session, document_id, user_id)
            version = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == version_id,
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.user_id == user_id,
                )
            )
            source = session.get(SourceSnapshot, version_id)
            if version is None or source is None:
                raise VersionNotFound("文档版本不存在或原文已删除")
            return version_view(version, source)

    def list_versions(
        self, document_id: str, user_id: str
    ) -> tuple[DocumentVersionView, ...]:
        """按新到旧列出文档的全部历史版本。"""
        with self._database.session() as session:
            require_document(session, document_id, user_id)
            rows = session.execute(
                select(DocumentVersion, SourceSnapshot)
                .join(SourceSnapshot, SourceSnapshot.version_id == DocumentVersion.id)
                .where(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.user_id == user_id,
                )
                .order_by(DocumentVersion.version.desc())
            ).all()
            return tuple(version_view(version, source) for version, source in rows)

    def archive(self, document_id: str, user_id: str) -> None:
        """归档后立即从默认列表和检索中过滤，但保留版本。"""
        self._set_status(document_id, user_id, "archived")

    def restore(self, document_id: str, user_id: str) -> None:
        """恢复归档文档，只有当前版本 ready 时才会重新进入检索。"""
        self._set_status(document_id, user_id, "active")

    def _set_status(self, document_id: str, user_id: str, status: str) -> None:
        with self._database.transaction() as session:
            document = require_document(session, document_id, user_id)
            document.status = status
            document.updated_at = datetime.now(UTC)

    def delete(self, document_id: str, user_id: str) -> None:
        """显式清除正文、历史版本、索引、组织关系和批量结果关联。"""
        file_object_ids: tuple[str, ...]
        with self._database.transaction() as session:
            require_document(session, document_id, user_id)
            file_object_ids = tuple(
                value
                for value in session.scalars(
                    select(SourceSnapshot.file_object_id).where(
                        SourceSnapshot.document_id == document_id,
                        SourceSnapshot.file_object_id.is_not(None),
                    )
                ).all()
                if value is not None
            )
            session.execute(
                delete(DocumentRelation).where(
                    or_(
                        DocumentRelation.source_document_id == document_id,
                        DocumentRelation.target_document_id == document_id,
                    )
                )
            )
            session.execute(
                delete(DocumentTag).where(DocumentTag.document_id == document_id)
            )
            session.execute(
                delete(KnowledgeRelation).where(
                    KnowledgeRelation.document_id == document_id
                )
            )
            session.execute(
                delete(KnowledgePointEntity).where(
                    KnowledgePointEntity.document_id == document_id
                )
            )
            session.execute(
                delete(KnowledgePoint).where(KnowledgePoint.document_id == document_id)
            )
            session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            session.execute(
                delete(DocumentIndexTask).where(
                    DocumentIndexTask.document_id == document_id
                )
            )
            session.execute(
                delete(SourceSnapshot).where(SourceSnapshot.document_id == document_id)
            )
            session.execute(
                delete(DocumentVersion).where(
                    DocumentVersion.document_id == document_id
                )
            )
            imported_items = session.scalars(
                select(ImportItem).where(ImportItem.document_id == document_id)
            ).all()
            for item in imported_items:
                item.document_id = None
                item.error_message = "原文已删除"
            session.execute(delete(Document).where(Document.id == document_id))
            session.execute(
                delete(KnowledgeEntity).where(
                    KnowledgeEntity.user_id == user_id,
                    ~KnowledgeEntity.id.in_(select(KnowledgePointEntity.entity_id)),
                )
            )
        if self._file_storage is not None:
            for file_object_id in set(file_object_ids):
                self._file_storage.delete(file_object_id)
