"""文档切分与索引刷新。

本文件只把指定版本转成可检索片段并维护刷新状态，不修改标题、专题或标签。
每次刷新都绑定 document_id + version_id，旧任务不能覆盖较新的当前版本。
"""

import json
import re
from datetime import UTC, datetime
from itertools import combinations
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from server.documents.errors import DocumentNotFound, InvalidDocumentInput
from server.documents.models import (
    Document,
    DocumentChunk,
    DocumentIndexTask,
    DocumentVersion,
    KnowledgeEntity,
    KnowledgePoint,
    KnowledgePointEntity,
    KnowledgeRelation,
)
from server.documents.types import RefreshRequest, RefreshStatusView
from server.infra.database import Database
from server.infra.embeddings import EmbeddingClient, FakeEmbeddingClient

_MAX_CHUNK_LENGTH = 900
_CHUNK_OVERLAP = 120
_LATIN_TOKEN = re.compile(r"[a-zA-Z0-9_+#.-]+")
_CJK_SEQUENCE = re.compile(r"[\u3400-\u9fff]+")
_KNOWLEDGE_LINE = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)(.+)$")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？.!?])\s+|\n+")
_WIKI_ENTITY = re.compile(r"\[\[([^\]]{2,200})\]\]")
_CODE_ENTITY = re.compile(r"`([^`\n]{2,200})`")
_HASH_ENTITY = re.compile(r"(?<!\w)#([\w\u3400-\u9fff][\w.+#-]{1,80})")
_TECH_ENTITY = re.compile(r"\b(?:[A-Z]{2,}|[A-Z][A-Za-z0-9]*(?:[.+#-][A-Za-z0-9]+)+)\b")


def tokenize(text: str) -> list[str]:
    """同时生成英文词和中文双字片段，保证中英文资料都能本地检索。"""
    lowered = text.casefold()
    tokens = _LATIN_TOKEN.findall(lowered)
    for sequence in _CJK_SEQUENCE.findall(lowered):
        if len(sequence) == 1:
            tokens.append(sequence)
        else:
            tokens.extend(
                sequence[index : index + 2] for index in range(len(sequence) - 1)
            )
    return tokens


def embedding_literal(values: tuple[float, ...]) -> str:
    """生成 pgvector 可安全绑定的向量字面量。"""
    return "[" + ",".join(f"{value:.9f}" for value in values) + "]"


def split_content(content: str) -> tuple[str, ...]:
    """优先按段落切分，超长段落使用重叠窗口保留上下文连续性。"""
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()
    ]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > _MAX_CHUNK_LENGTH:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + _MAX_CHUNK_LENGTH])
                if start + _MAX_CHUNK_LENGTH >= len(paragraph):
                    break
                start += _MAX_CHUNK_LENGTH - _CHUNK_OVERLAP
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= _MAX_CHUNK_LENGTH:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return tuple(chunks)


def extract_knowledge_points(content: str) -> tuple[str, ...]:
    """优先提取标题和列表结论，再以完整句子补充可追溯知识点。"""
    explicit = [
        match.group(1).strip()
        for line in content.splitlines()
        if (match := _KNOWLEDGE_LINE.match(line)) is not None
    ]
    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_BOUNDARY.split(content)
        if 8 <= len(sentence.strip()) <= 300
    ]
    values = explicit + sentences
    if not values:
        values = [content[:300].strip()]
    return tuple(dict.fromkeys(value for value in values if value))[:24]


def extract_entities(content: str) -> tuple[tuple[str, str], ...]:
    """只提取用户显式标记或格式明显的实体，避免模型猜测造成知识污染。"""
    candidates: list[tuple[str, str]] = []
    candidates.extend(
        (value.strip(), "wiki") for value in _WIKI_ENTITY.findall(content)
    )
    candidates.extend(
        (value.strip(), "code") for value in _CODE_ENTITY.findall(content)
    )
    candidates.extend(
        (value.strip(), "hashtag") for value in _HASH_ENTITY.findall(content)
    )
    candidates.extend(
        (value.strip(), "technical") for value in _TECH_ENTITY.findall(content)
    )
    unique: dict[str, tuple[str, str]] = {}
    for name, entity_type in candidates:
        normalized = " ".join(name.split()).casefold()
        if normalized and normalized not in unique:
            unique[normalized] = (" ".join(name.split()), entity_type)
    return tuple(unique.values())


class DocumentIndexer:
    """幂等生成当前版本片段并维护 queued/processing/ready/failed 状态。"""

    def __init__(
        self,
        database: Database,
        embeddings: EmbeddingClient | None = None,
    ) -> None:
        self._database = database
        self._embeddings = embeddings or FakeEmbeddingClient()

    @staticmethod
    def queue_in_transaction(
        session: Session, document_id: str, version_id: str, user_id: str
    ) -> None:
        """在版本事务内写入唯一任务，避免版本已提交但任务丢失。"""
        session.add(
            DocumentIndexTask(
                id=str(uuid4()),
                user_id=user_id,
                document_id=document_id,
                version_id=version_id,
                status="queued",
            )
        )

    def refresh(self, request: RefreshRequest) -> None:
        """刷新一个版本；版本已经过期时直接结束且不改当前文档状态。"""
        with self._database.transaction() as session:
            document = session.scalar(
                select(Document).where(Document.id == request.document_id)
            )
            version = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == request.version_id,
                    DocumentVersion.document_id == request.document_id,
                )
            )
            if document is None or version is None:
                raise DocumentNotFound("待刷新的文档版本不存在")
            if document.current_version_id != request.version_id:
                task = session.scalar(
                    select(DocumentIndexTask).where(
                        DocumentIndexTask.document_id == request.document_id,
                        DocumentIndexTask.version_id == request.version_id,
                    )
                )
                if task is not None:
                    task.status = "completed"
                    task.error_message = "版本已被更新，无需发布旧索引"
                return
            task = session.scalar(
                select(DocumentIndexTask).where(
                    DocumentIndexTask.document_id == request.document_id,
                    DocumentIndexTask.version_id == request.version_id,
                )
            )
            if task is None:
                task = DocumentIndexTask(
                    id=str(uuid4()),
                    user_id=version.user_id,
                    document_id=request.document_id,
                    version_id=request.version_id,
                    status="queued",
                )
                session.add(task)
            task.status = "processing"
            task.attempt_count += 1
            task.error_message = None
            task.updated_at = datetime.now(UTC)
            version.index_status = "processing"
            version.index_error = None
            version.index_updated_at = datetime.now(UTC)
            document.index_status = "processing"
            content = version.content_snapshot
            user_id = version.user_id

        try:
            pieces = split_content(content)
            if not pieces:
                raise InvalidDocumentInput("文档正文不能为空")
            # 外部 Embedding 调用在事务外完成，避免模型延迟长期占用数据库事务。
            indexed_pieces = tuple(
                (piece, self._embeddings.embed(piece)) for piece in pieces
            )
            with self._database.transaction() as session:
                # 再次读取当前版本，防止较慢的旧任务覆盖刚创建的新版本。
                document = session.scalar(
                    select(Document).where(Document.id == request.document_id)
                )
                version = session.scalar(
                    select(DocumentVersion).where(
                        DocumentVersion.id == request.version_id,
                        DocumentVersion.document_id == request.document_id,
                    )
                )
                if document is None or version is None:
                    return
                if document.current_version_id != request.version_id:
                    return
                session.execute(
                    delete(KnowledgeRelation).where(
                        KnowledgeRelation.version_id == request.version_id
                    )
                )
                session.execute(
                    delete(KnowledgePointEntity).where(
                        KnowledgePointEntity.version_id == request.version_id
                    )
                )
                session.execute(
                    delete(KnowledgePoint).where(
                        KnowledgePoint.version_id == request.version_id
                    )
                )
                session.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.version_id == request.version_id
                    )
                )
                point_position = 0
                entity_cache: dict[str, KnowledgeEntity] = {}
                for position, (piece, embedding) in enumerate(indexed_pieces):
                    chunk_id = str(uuid4())
                    session.add(
                        DocumentChunk(
                            id=chunk_id,
                            user_id=user_id,
                            document_id=request.document_id,
                            version_id=request.version_id,
                            position=position,
                            content=piece,
                            search_text=piece.casefold(),
                            vector_json=json.dumps(embedding),
                            embedding=embedding_literal(embedding),
                        )
                    )
                    session.flush()
                    for point_content in extract_knowledge_points(piece):
                        point = KnowledgePoint(
                            id=str(uuid4()),
                            user_id=user_id,
                            document_id=request.document_id,
                            version_id=request.version_id,
                            chunk_id=chunk_id,
                            position=point_position,
                            content=point_content,
                        )
                        point_position += 1
                        session.add(point)
                        session.flush()
                        point_entities: list[KnowledgeEntity] = []
                        for entity_name, entity_type in extract_entities(point_content):
                            normalized = entity_name.casefold()
                            entity = entity_cache.get(normalized)
                            if entity is None:
                                entity = session.scalar(
                                    select(KnowledgeEntity).where(
                                        KnowledgeEntity.user_id == user_id,
                                        KnowledgeEntity.normalized_name == normalized,
                                    )
                                )
                            if entity is None:
                                entity = KnowledgeEntity(
                                    id=str(uuid4()),
                                    user_id=user_id,
                                    name=entity_name,
                                    normalized_name=normalized,
                                    entity_type=entity_type,
                                )
                                session.add(entity)
                                session.flush()
                            entity_cache[normalized] = entity
                            point_entities.append(entity)
                            session.add(
                                KnowledgePointEntity(
                                    point_id=point.id,
                                    entity_id=entity.id,
                                    user_id=user_id,
                                    document_id=request.document_id,
                                    version_id=request.version_id,
                                )
                            )
                        session.flush()
                        ordered_entities = sorted(
                            {entity.id: entity for entity in point_entities}.values(),
                            key=lambda entity: entity.id,
                        )
                        for source_entity, target_entity in combinations(
                            ordered_entities, 2
                        ):
                            session.add(
                                KnowledgeRelation(
                                    id=str(uuid4()),
                                    user_id=user_id,
                                    document_id=request.document_id,
                                    version_id=request.version_id,
                                    point_id=point.id,
                                    source_entity_id=source_entity.id,
                                    target_entity_id=target_entity.id,
                                    relation_type="co_occurs",
                                )
                            )
                now = datetime.now(UTC)
                version.index_status = "ready"
                version.index_error = None
                version.index_updated_at = now
                document.index_status = "ready"
                document.updated_at = now
                task = session.scalar(
                    select(DocumentIndexTask).where(
                        DocumentIndexTask.document_id == request.document_id,
                        DocumentIndexTask.version_id == request.version_id,
                    )
                )
                if task is not None:
                    task.status = "completed"
                    task.error_message = None
                    task.updated_at = now
        except Exception as exc:
            self._mark_failed(request, str(exc))
            raise

    def _mark_failed(self, request: RefreshRequest, message: str) -> None:
        """只允许仍为当前版本的失败任务发布 failed。"""
        with self._database.transaction() as session:
            document = session.scalar(
                select(Document).where(Document.id == request.document_id)
            )
            version = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == request.version_id,
                    DocumentVersion.document_id == request.document_id,
                )
            )
            if (
                document is None
                or version is None
                or document.current_version_id != request.version_id
            ):
                return
            now = datetime.now(UTC)
            version.index_status = "failed"
            version.index_error = message[:1000]
            version.index_updated_at = now
            document.index_status = "failed"
            task = session.scalar(
                select(DocumentIndexTask).where(
                    DocumentIndexTask.document_id == request.document_id,
                    DocumentIndexTask.version_id == request.version_id,
                )
            )
            if task is not None:
                task.status = "failed"
                task.error_message = message[:1000]
                task.updated_at = now

    def refresh_queued(self, limit: int = 100) -> int:
        """供定时任务扫描 queued 任务；failed 只由显式重试再次执行。"""
        if limit < 1 or limit > 1000:
            raise InvalidDocumentInput("索引扫描条数必须在 1 到 1000 之间")
        with self._database.session() as session:
            requests = tuple(
                RefreshRequest(document_id=task.document_id, version_id=task.version_id)
                for task in session.scalars(
                    select(DocumentIndexTask)
                    .where(DocumentIndexTask.status == "queued")
                    .order_by(DocumentIndexTask.updated_at)
                    .limit(limit)
                ).all()
            )
        for request in requests:
            try:
                self.refresh(request)
            except Exception:
                # 单个任务失败已经记录，不阻塞后续版本修复。
                continue
        return len(requests)

    def get_status(self, document_id: str, user_id: str) -> RefreshStatusView:
        """查询属于当前用户的文档最新版本索引状态。"""
        with self._database.session() as session:
            row = session.execute(
                select(Document, DocumentVersion)
                .join(
                    DocumentVersion,
                    DocumentVersion.id == Document.current_version_id,
                )
                .where(Document.id == document_id, Document.user_id == user_id)
            ).one_or_none()
            if row is None:
                raise DocumentNotFound("文档不存在")
            document, version = row
            return RefreshStatusView(
                document_id=document.id,
                version_id=version.id,
                status=version.index_status,
                error_message=version.index_error,
                updated_at=version.index_updated_at,
            )
