"""当前文档知识点、实体和关系的只读查询。"""

from sqlalchemy import select

from server.documents.documents import require_document
from server.documents.models import (
    KnowledgeEntity,
    KnowledgePoint,
    KnowledgePointEntity,
    KnowledgeRelation,
)
from server.documents.types import (
    DocumentKnowledgeView,
    KnowledgeEntityView,
    KnowledgePointView,
    KnowledgeRelationView,
)
from server.infra.database import Database


class DocumentKnowledge:
    """只读取 documents 已生成的数据，不推断新关系也不承担 Agent 推理。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, document_id: str, user_id: str) -> DocumentKnowledgeView:
        """返回属于当前用户的文档当前版本知识结构。"""
        with self._database.session() as session:
            document = require_document(session, document_id, user_id)
            points = session.scalars(
                select(KnowledgePoint)
                .where(
                    KnowledgePoint.user_id == user_id,
                    KnowledgePoint.document_id == document_id,
                    KnowledgePoint.version_id == document.current_version_id,
                )
                .order_by(KnowledgePoint.position)
            ).all()
            point_ids = tuple(point.id for point in points)
            mentions = (
                session.scalars(
                    select(KnowledgePointEntity).where(
                        KnowledgePointEntity.user_id == user_id,
                        KnowledgePointEntity.version_id == document.current_version_id,
                    )
                ).all()
                if point_ids
                else []
            )
            entity_ids = tuple({mention.entity_id for mention in mentions})
            entities = (
                session.scalars(
                    select(KnowledgeEntity)
                    .where(
                        KnowledgeEntity.user_id == user_id,
                        KnowledgeEntity.id.in_(entity_ids),
                    )
                    .order_by(KnowledgeEntity.name)
                ).all()
                if entity_ids
                else []
            )
            relations = session.scalars(
                select(KnowledgeRelation).where(
                    KnowledgeRelation.user_id == user_id,
                    KnowledgeRelation.document_id == document_id,
                    KnowledgeRelation.version_id == document.current_version_id,
                )
            ).all()
            mentions_by_point: dict[str, list[str]] = {}
            for mention in mentions:
                mentions_by_point.setdefault(mention.point_id, []).append(
                    mention.entity_id
                )
            return DocumentKnowledgeView(
                document_id=document.id,
                version_id=document.current_version_id,
                points=tuple(
                    KnowledgePointView(
                        id=point.id,
                        chunk_id=point.chunk_id,
                        position=point.position,
                        content=point.content,
                        entity_ids=tuple(mentions_by_point.get(point.id, ())),
                    )
                    for point in points
                ),
                entities=tuple(
                    KnowledgeEntityView(
                        id=entity.id,
                        name=entity.name,
                        entity_type=entity.entity_type,
                    )
                    for entity in entities
                ),
                relations=tuple(
                    KnowledgeRelationView(
                        id=relation.id,
                        point_id=relation.point_id,
                        source_entity_id=relation.source_entity_id,
                        target_entity_id=relation.target_entity_id,
                        relation_type=relation.relation_type,
                    )
                    for relation in relations
                ),
            )
