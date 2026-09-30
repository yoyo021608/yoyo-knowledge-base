"""面向 Agent 和用户的知识候选查询端口。

本文件只返回经过用户归属、文档状态和当前 ready 版本校验的候选片段。查询改写、
重排、证据判断和回答生成均属于 agent 模块，不在这里实现。
"""

import json
from collections.abc import Sequence
from typing import cast

from sqlalchemy import select, text

from server.documents.errors import InvalidDocumentInput
from server.documents.indexing import embedding_literal, tokenize
from server.documents.models import (
    Document,
    DocumentChunk,
    DocumentTag,
    DocumentVersion,
    SourceSnapshot,
    Tag,
)
from server.documents.types import SearchHit, SearchQuery
from server.infra.database import Database
from server.infra.embeddings import EmbeddingClient, FakeEmbeddingClient

_SEARCH_MODES = {"keyword", "full_text", "vector", "hybrid"}
_MAX_CANDIDATE_ROWS = 2000


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """计算两个已归一化 Embedding 的余弦相似度。"""
    if len(left) != len(right):
        return 0.0
    return sum(left[index] * right[index] for index in range(len(left)))


def _scores(
    query_text: str,
    content: str,
    vector_json: str,
    query_embedding: Sequence[float],
) -> tuple[float, float, float]:
    """分别计算原词命中、全文覆盖和语义近似分数。"""
    normalized_query = query_text.casefold().strip()
    normalized_content = content.casefold()
    keyword_score = 0.0
    if normalized_query:
        occurrences = normalized_content.count(normalized_query)
        keyword_score = min(1.0, occurrences / 3) if occurrences else 0.0

    query_tokens = set(tokenize(normalized_query))
    content_tokens = set(tokenize(normalized_content))
    full_text_score = (
        len(query_tokens & content_tokens) / len(query_tokens) if query_tokens else 0.0
    )
    stored_vector = cast(list[float], json.loads(vector_json))
    vector_score = max(0.0, _cosine(query_embedding, stored_vector))
    return keyword_score, full_text_score, vector_score


class DocumentSearch:
    """在 documents 拥有的片段中检索并复核候选来源。"""

    def __init__(
        self,
        database: Database,
        embeddings: EmbeddingClient | None = None,
    ) -> None:
        self._database = database
        self._embeddings = embeddings or FakeEmbeddingClient()

    def search(self, query: SearchQuery) -> tuple[SearchHit, ...]:
        """按请求模式评分，且只读取当前用户 active + ready 的当前版本。"""
        text = query.text.strip()
        if not text:
            raise InvalidDocumentInput("检索内容不能为空")
        if query.mode not in _SEARCH_MODES:
            raise InvalidDocumentInput("检索模式不受支持")
        if query.limit < 1 or query.limit > 50:
            raise InvalidDocumentInput("检索条数必须在 1 到 50 之间")
        query_embedding = self._embeddings.embed(text)

        if self._database.engine.dialect.name == "postgresql":
            return self._search_postgresql(query, text, query_embedding)

        with self._database.session() as session:
            statement = (
                select(DocumentChunk, Document, SourceSnapshot)
                .join(Document, Document.id == DocumentChunk.document_id)
                .join(
                    DocumentVersion,
                    DocumentVersion.id == DocumentChunk.version_id,
                )
                .join(
                    SourceSnapshot,
                    SourceSnapshot.version_id == DocumentChunk.version_id,
                )
                .where(
                    DocumentChunk.user_id == query.user_id,
                    Document.user_id == query.user_id,
                    Document.status == "active",
                    Document.index_status == "ready",
                    Document.current_version_id == DocumentChunk.version_id,
                    DocumentVersion.index_status == "ready",
                )
            )
            if query.topic_id is not None:
                statement = statement.where(Document.topic_id == query.topic_id)
            if query.tag:
                statement = (
                    statement.join(DocumentTag, DocumentTag.document_id == Document.id)
                    .join(Tag, Tag.id == DocumentTag.tag_id)
                    .where(Tag.user_id == query.user_id, Tag.name == query.tag.strip())
                )
            rows = session.execute(
                statement.distinct().limit(_MAX_CANDIDATE_ROWS)
            ).all()

        hits: list[SearchHit] = []
        for chunk, document, source in rows:
            keyword, full_text, vector = _scores(
                text,
                chunk.content,
                chunk.vector_json,
                query_embedding,
            )
            if query.mode == "keyword":
                score = keyword
            elif query.mode == "full_text":
                score = full_text
            elif query.mode == "vector":
                score = vector
            else:
                # 混合检索保留精确短语优势，同时兼顾词覆盖和相近表达。
                score = keyword * 0.35 + full_text * 0.30 + vector * 0.35
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    document_id=document.id,
                    version_id=chunk.version_id,
                    title=document.title,
                    content_snippet=chunk.content,
                    chunk_id=chunk.id,
                    source_url=source.source_url,
                    score=round(score, 6),
                )
            )
        hits.sort(key=lambda item: (-item.score, item.document_id, item.chunk_id))
        return tuple(hits[: query.limit])

    def _search_postgresql(
        self,
        query: SearchQuery,
        text_value: str,
        query_embedding: tuple[float, ...],
    ) -> tuple[SearchHit, ...]:
        """使用 PostgreSQL 全文索引和 pgvector 计算基础候选分数。"""
        statement = text("""
            WITH scored AS (
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.version_id,
                    d.title,
                    c.content AS content_snippet,
                    s.source_url,
                    CASE WHEN position(lower(:query_text) IN lower(c.content)) > 0
                         THEN 1.0 ELSE 0.0 END AS keyword_score,
                    ts_rank_cd(
                        to_tsvector('simple', c.search_text),
                        plainto_tsquery('simple', :query_text)
                    ) AS full_text_score,
                    GREATEST(
                        0.0,
                        1.0 - (c.embedding <=> CAST(:embedding AS vector))
                    ) AS vector_score
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN document_versions v ON v.id = c.version_id
                JOIN document_source_snapshots s ON s.version_id = c.version_id
                WHERE c.user_id = :user_id
                  AND d.user_id = :user_id
                  AND d.status = 'active'
                  AND d.index_status = 'ready'
                  AND d.current_version_id = c.version_id
                  AND v.index_status = 'ready'
                  AND (
                      CAST(:topic_id AS varchar) IS NULL
                      OR d.topic_id = CAST(:topic_id AS varchar)
                  )
                  AND (
                      CAST(:tag AS varchar) IS NULL OR EXISTS (
                          SELECT 1
                          FROM document_tag_links dt
                          JOIN document_tags t ON t.id = dt.tag_id
                          WHERE dt.document_id = d.id
                            AND dt.user_id = :user_id
                            AND t.name = CAST(:tag AS varchar)
                      )
                  )
            ), ranked AS (
                SELECT *,
                    CASE CAST(:mode AS varchar)
                        WHEN 'keyword' THEN keyword_score
                        WHEN 'full_text' THEN full_text_score
                        WHEN 'vector' THEN vector_score
                        ELSE keyword_score * 0.35
                           + full_text_score * 0.30
                           + vector_score * 0.35
                    END AS score
                FROM scored
            )
            SELECT * FROM ranked
            WHERE score > 0
            ORDER BY score DESC, document_id, chunk_id
            LIMIT :limit
            """)
        with self._database.session() as session:
            rows = session.execute(
                statement,
                {
                    "query_text": text_value,
                    "embedding": embedding_literal(query_embedding),
                    "user_id": query.user_id,
                    "topic_id": query.topic_id,
                    "tag": query.tag.strip() if query.tag else None,
                    "mode": query.mode,
                    "limit": query.limit,
                },
            ).mappings()
            return tuple(
                SearchHit(
                    document_id=str(row["document_id"]),
                    version_id=str(row["version_id"]),
                    title=str(row["title"]),
                    content_snippet=str(row["content_snippet"]),
                    chunk_id=str(row["chunk_id"]),
                    source_url=(
                        str(row["source_url"])
                        if row["source_url"] is not None
                        else None
                    ),
                    score=round(float(row["score"]), 6),
                )
                for row in rows
            )

    def validate_sources(
        self, user_id: str, hits: tuple[SearchHit, ...]
    ) -> tuple[SearchHit, ...]:
        """重新读取持久化片段，排除伪造、删除、归档或已过期的候选。"""
        validated: list[SearchHit] = []
        with self._database.session() as session:
            for candidate in hits:
                row = session.execute(
                    select(DocumentChunk, Document, DocumentVersion, SourceSnapshot)
                    .join(Document, Document.id == DocumentChunk.document_id)
                    .join(
                        DocumentVersion,
                        DocumentVersion.id == DocumentChunk.version_id,
                    )
                    .join(
                        SourceSnapshot,
                        SourceSnapshot.version_id == DocumentChunk.version_id,
                    )
                    .where(
                        DocumentChunk.id == candidate.chunk_id,
                        DocumentChunk.user_id == user_id,
                        DocumentChunk.document_id == candidate.document_id,
                        DocumentChunk.version_id == candidate.version_id,
                        Document.user_id == user_id,
                        Document.status == "active",
                        Document.index_status == "ready",
                        Document.current_version_id == candidate.version_id,
                        DocumentVersion.index_status == "ready",
                    )
                ).one_or_none()
                if row is None:
                    continue
                chunk, document, _version, source = row
                validated.append(
                    SearchHit(
                        document_id=document.id,
                        version_id=chunk.version_id,
                        title=document.title,
                        content_snippet=chunk.content,
                        chunk_id=chunk.id,
                        source_url=source.source_url,
                        score=candidate.score,
                    )
                )
        return tuple(validated)
