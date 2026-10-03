"""在装配边界把 documents 的公开检索契约转换为 Agent 端口。"""

from server.agent.types import RetrievalPlan, SearchHitContext
from server.documents.module import DocumentsModule
from server.documents.types import SearchHit, SearchQuery


def _agent_hit(value: SearchHit) -> SearchHitContext:
    return SearchHitContext(
        document_id=value.document_id,
        version_id=value.version_id,
        title=value.title,
        content_snippet=value.content_snippet,
        chunk_id=value.chunk_id,
        source_url=value.source_url,
        score=value.score,
    )


def _document_hit(value: SearchHitContext) -> SearchHit:
    return SearchHit(
        document_id=value.document_id,
        version_id=value.version_id,
        title=value.title,
        content_snippet=value.content_snippet,
        chunk_id=value.chunk_id,
        source_url=value.source_url,
        score=value.score,
    )


class DocumentsSearchBridge:
    """唯一允许同时认识 Agent 契约与 documents 公开类型的适配器。"""

    def __init__(self, documents: DocumentsModule) -> None:
        self._documents = documents

    def search(self, user_id: str, plan: RetrievalPlan) -> tuple[SearchHitContext, ...]:
        values = self._documents.search.search(
            SearchQuery(
                user_id=user_id,
                text=plan.query,
                mode=plan.mode,
                topic_id=plan.topic_id,
                tag=plan.tag,
                limit=plan.limit,
                document_ids=plan.document_ids,
                version_ids=plan.version_ids,
            )
        )
        return tuple(_agent_hit(value) for value in values)

    def validate_sources(
        self,
        user_id: str,
        hits: tuple[SearchHitContext, ...],
        *,
        allow_historical_versions: bool = False,
    ) -> tuple[SearchHitContext, ...]:
        values = self._documents.search.validate_sources(
            user_id,
            tuple(_document_hit(value) for value in hits),
            allow_historical_versions=allow_historical_versions,
        )
        return tuple(_agent_hit(value) for value in values)
