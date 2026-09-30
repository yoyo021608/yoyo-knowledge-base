"""专题、标签、收藏和文档关联。

本文件只维护知识组织关系，不读取或修改版本正文，也不参与索引评分。
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, or_, select

from server.documents.documents import require_document
from server.documents.errors import (
    DuplicateName,
    InvalidDocumentInput,
    RelationNotFound,
    TagNotFound,
    TopicNotFound,
)
from server.documents.models import (
    Document,
    DocumentRelation,
    DocumentTag,
    Tag,
    Topic,
)
from server.documents.types import (
    DocumentRelationView,
    RelationInput,
    TagView,
    TopicInput,
    TopicView,
)
from server.infra.database import Database


def _name(value: str, maximum: int, field_name: str) -> str:
    """统一专题、标签和关系名称的空白与长度。"""
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise InvalidDocumentInput(f"{field_name}不能为空")
    if len(normalized) > maximum:
        raise InvalidDocumentInput(f"{field_name}不能超过 {maximum} 个字符")
    return normalized


def _topic_view(topic: Topic) -> TopicView:
    return TopicView(
        id=topic.id,
        user_id=topic.user_id,
        name=topic.name,
        description=topic.description,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
    )


def _tag_view(tag: Tag) -> TagView:
    return TagView(
        id=tag.id,
        user_id=tag.user_id,
        name=tag.name,
        created_at=tag.created_at,
    )


def _relation_view(relation: DocumentRelation) -> DocumentRelationView:
    return DocumentRelationView(
        id=relation.id,
        user_id=relation.user_id,
        source_document_id=relation.source_document_id,
        target_document_id=relation.target_document_id,
        relation_type=relation.relation_type,
        created_at=relation.created_at,
    )


class KnowledgeOrganization:
    """维护用户范围内的专题、标签、收藏和文档关系。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_topic(self, user_id: str, topic_input: TopicInput) -> TopicView:
        """创建专题；同一用户不能创建重名专题。"""
        name = _name(topic_input.name, 100, "专题名")
        description = topic_input.description.strip()
        with self._database.transaction() as session:
            existing = session.scalar(
                select(Topic).where(Topic.user_id == user_id, Topic.name == name)
            )
            if existing is not None:
                raise DuplicateName("专题名已存在")
            topic = Topic(
                id=str(uuid4()),
                user_id=user_id,
                name=name,
                description=description,
            )
            session.add(topic)
            session.flush()
            return _topic_view(topic)

    def list_topics(self, user_id: str) -> tuple[TopicView, ...]:
        """按最近更新顺序返回当前用户专题。"""
        with self._database.session() as session:
            topics = session.scalars(
                select(Topic)
                .where(Topic.user_id == user_id)
                .order_by(Topic.updated_at.desc())
            ).all()
            return tuple(_topic_view(topic) for topic in topics)

    def update_topic(
        self, user_id: str, topic_id: str, topic_input: TopicInput
    ) -> TopicView:
        """更新专题信息，不改变专题内文档正文。"""
        name = _name(topic_input.name, 100, "专题名")
        with self._database.transaction() as session:
            topic = session.scalar(
                select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
            )
            if topic is None:
                raise TopicNotFound("专题不存在")
            duplicate = session.scalar(
                select(Topic).where(
                    Topic.user_id == user_id,
                    Topic.name == name,
                    Topic.id != topic_id,
                )
            )
            if duplicate is not None:
                raise DuplicateName("专题名已存在")
            topic.name = name
            topic.description = topic_input.description.strip()
            topic.updated_at = datetime.now(UTC)
            session.flush()
            return _topic_view(topic)

    def delete_topic(self, user_id: str, topic_id: str) -> None:
        """解除文档归类后删除专题，不删除任何文档。"""
        with self._database.transaction() as session:
            topic = session.scalar(
                select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
            )
            if topic is None:
                raise TopicNotFound("专题不存在")
            documents = session.scalars(
                select(Document).where(
                    Document.user_id == user_id, Document.topic_id == topic_id
                )
            ).all()
            for document in documents:
                document.topic_id = None
            session.delete(topic)

    def create_tag(self, user_id: str, name: str) -> TagView:
        """创建用户标签；同一用户不能创建重名标签。"""
        normalized = _name(name, 60, "标签名")
        with self._database.transaction() as session:
            existing = session.scalar(
                select(Tag).where(Tag.user_id == user_id, Tag.name == normalized)
            )
            if existing is not None:
                raise DuplicateName("标签名已存在")
            tag = Tag(id=str(uuid4()), user_id=user_id, name=normalized)
            session.add(tag)
            session.flush()
            return _tag_view(tag)

    def list_tags(self, user_id: str) -> tuple[TagView, ...]:
        """按名称列出当前用户标签。"""
        with self._database.session() as session:
            tags = session.scalars(
                select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
            ).all()
            return tuple(_tag_view(tag) for tag in tags)

    def rename_tag(self, user_id: str, tag_id: str, name: str) -> TagView:
        """修改标签名称并保留已有文档关联。"""
        normalized = _name(name, 60, "标签名")
        with self._database.transaction() as session:
            tag = session.scalar(
                select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
            )
            if tag is None:
                raise TagNotFound("标签不存在")
            duplicate = session.scalar(
                select(Tag).where(
                    Tag.user_id == user_id,
                    Tag.name == normalized,
                    Tag.id != tag_id,
                )
            )
            if duplicate is not None:
                raise DuplicateName("标签名已存在")
            tag.name = normalized
            session.flush()
            return _tag_view(tag)

    def delete_tag(self, user_id: str, tag_id: str) -> None:
        """解除所有文档标记后删除标签，不删除文档。"""
        with self._database.transaction() as session:
            tag = session.scalar(
                select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
            )
            if tag is None:
                raise TagNotFound("标签不存在")
            session.execute(
                delete(DocumentTag).where(
                    DocumentTag.tag_id == tag_id, DocumentTag.user_id == user_id
                )
            )
            session.delete(tag)

    def attach_tag(self, document_id: str, tag_id: str, user_id: str) -> None:
        """给当前用户文档附加当前用户标签，重复调用保持幂等。"""
        with self._database.transaction() as session:
            require_document(session, document_id, user_id)
            tag = session.scalar(
                select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
            )
            if tag is None:
                raise TagNotFound("标签不存在")
            link = session.scalar(
                select(DocumentTag).where(
                    DocumentTag.document_id == document_id,
                    DocumentTag.tag_id == tag_id,
                )
            )
            if link is None:
                session.add(
                    DocumentTag(document_id=document_id, tag_id=tag_id, user_id=user_id)
                )

    def detach_tag(self, document_id: str, tag_id: str, user_id: str) -> None:
        """取消文档标签；标签本身继续保留。"""
        with self._database.transaction() as session:
            require_document(session, document_id, user_id)
            tag = session.scalar(
                select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
            )
            if tag is None:
                raise TagNotFound("标签不存在")
            session.execute(
                delete(DocumentTag).where(
                    DocumentTag.document_id == document_id,
                    DocumentTag.tag_id == tag_id,
                )
            )

    def set_favorite(self, document_id: str, user_id: str, favorite: bool) -> None:
        """设置或取消收藏，不产生文档新版本。"""
        with self._database.transaction() as session:
            document = require_document(session, document_id, user_id)
            document.is_favorite = favorite
            document.updated_at = datetime.now(UTC)

    def create_relation(self, relation_input: RelationInput) -> DocumentRelationView:
        """在两个属于同一用户的不同文档之间建立关联。"""
        relation_type = _name(relation_input.relation_type, 60, "关联类型")
        if relation_input.source_document_id == relation_input.target_document_id:
            raise InvalidDocumentInput("文档不能关联自身")
        with self._database.transaction() as session:
            require_document(
                session, relation_input.source_document_id, relation_input.user_id
            )
            require_document(
                session, relation_input.target_document_id, relation_input.user_id
            )
            existing = session.scalar(
                select(DocumentRelation).where(
                    DocumentRelation.source_document_id
                    == relation_input.source_document_id,
                    DocumentRelation.target_document_id
                    == relation_input.target_document_id,
                    DocumentRelation.relation_type == relation_type,
                )
            )
            if existing is not None:
                return _relation_view(existing)
            relation = DocumentRelation(
                id=str(uuid4()),
                user_id=relation_input.user_id,
                source_document_id=relation_input.source_document_id,
                target_document_id=relation_input.target_document_id,
                relation_type=relation_type,
            )
            session.add(relation)
            session.flush()
            return _relation_view(relation)

    def list_relations(
        self, document_id: str, user_id: str
    ) -> tuple[DocumentRelationView, ...]:
        """列出以指定文档为起点或终点的全部关联。"""
        with self._database.session() as session:
            require_document(session, document_id, user_id)
            relations = session.scalars(
                select(DocumentRelation)
                .where(
                    DocumentRelation.user_id == user_id,
                    or_(
                        DocumentRelation.source_document_id == document_id,
                        DocumentRelation.target_document_id == document_id,
                    ),
                )
                .order_by(DocumentRelation.created_at.desc())
            ).all()
            return tuple(_relation_view(relation) for relation in relations)

    def delete_relation(self, relation_id: str, user_id: str) -> None:
        """删除当前用户拥有的文档关联。"""
        with self._database.transaction() as session:
            relation = session.scalar(
                select(DocumentRelation).where(
                    DocumentRelation.id == relation_id,
                    DocumentRelation.user_id == user_id,
                )
            )
            if relation is None:
                raise RelationNotFound("文档关联不存在")
            session.delete(relation)
