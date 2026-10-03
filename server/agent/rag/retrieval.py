"""制定检索计划并对 documents 候选做去重和重排。"""

from typing import cast

from server.agent.errors import InvalidAgentInput, RetrievalUnavailable
from server.agent.ports import DocumentSearchPort
from server.agent.rag.text import tokens
from server.agent.types import RetrievalPlan, SearchHitContext, SearchMode


class RetrievalOrchestrator:
    def __init__(self, port: DocumentSearchPort, default_limit: int = 8) -> None:
        self._port = port
        self._default_limit = default_limit

    def plan(
        self,
        question: str,
        *,
        topic_id: str | None = None,
        tag: str | None = None,
        mode: str = "hybrid",
        limit: int | None = None,
        document_ids: tuple[str, ...] = (),
        version_ids: tuple[str, ...] = (),
    ) -> RetrievalPlan:
        if not question.strip():
            raise InvalidAgentInput("检索问题不能为空")
        if mode not in {"keyword", "full_text", "vector", "hybrid"}:
            raise InvalidAgentInput("检索模式不受支持")
        selected_limit = limit if limit is not None else self._default_limit
        if not 1 <= selected_limit <= 50:
            raise InvalidAgentInput("检索条数必须在 1 到 50 之间")
        return RetrievalPlan(
            query=question.strip(),
            mode=cast(SearchMode, mode),
            limit=selected_limit,
            topic_id=topic_id,
            tag=tag,
            document_ids=document_ids,
            version_ids=version_ids,
        )

    def retrieve(
        self, plan: RetrievalPlan, user_id: str
    ) -> tuple[SearchHitContext, ...]:
        try:
            candidates = self._port.search(user_id, plan)
        except Exception as exc:
            raise RetrievalUnavailable("知识检索暂时不可用") from exc
        query_terms = set(tokens(plan.query))
        unique: dict[tuple[str, str, str], SearchHitContext] = {}
        for item in candidates:
            key = (item.document_id, item.version_id, item.chunk_id)
            overlap = len(query_terms & set(tokens(item.content_snippet)))
            adjusted = SearchHitContext(
                document_id=item.document_id,
                version_id=item.version_id,
                title=item.title,
                content_snippet=item.content_snippet,
                chunk_id=item.chunk_id,
                source_url=item.source_url,
                score=item.score + min(overlap, 5) * 0.02,
            )
            if key not in unique or adjusted.score > unique[key].score:
                unique[key] = adjusted
        return tuple(
            sorted(unique.values(), key=lambda value: (-value.score, value.chunk_id))[
                : plan.limit
            ]
        )
