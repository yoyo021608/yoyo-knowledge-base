"""Agent 访问知识的唯一端口；具体 documents 适配由装配层提供。"""

from typing import Protocol

from server.agent.types import RetrievalPlan, SearchHitContext


class DocumentSearchPort(Protocol):
    def search(
        self, user_id: str, plan: RetrievalPlan
    ) -> tuple[SearchHitContext, ...]: ...

    def validate_sources(
        self,
        user_id: str,
        hits: tuple[SearchHitContext, ...],
        *,
        allow_historical_versions: bool = False,
    ) -> tuple[SearchHitContext, ...]: ...
