"""按问题覆盖度判断证据，控制一次有界补查。"""

from server.agent.rag.text import tokens
from server.agent.types import EvidenceDecision, NextRetrieval, SearchHitContext


class EvidenceAssessor:
    def assess(
        self, question: str, hits: tuple[SearchHitContext, ...]
    ) -> EvidenceDecision:
        question_terms = tuple(dict.fromkeys(tokens(question)))
        if not hits:
            return EvidenceDecision(False, "没有检索到可用资料", 0, question_terms[:8])
        evidence_terms = set(
            token
            for hit in hits
            for token in tokens(hit.title + " " + hit.content_snippet)
        )
        meaningful = tuple(
            term
            for term in question_terms
            if len(term) > 1 or "\u4e00" <= term <= "\u9fff"
        )
        missing = tuple(term for term in meaningful if term not in evidence_terms)
        coverage = 1.0 if not meaningful else 1 - len(missing) / len(meaningful)
        sufficient = coverage >= 0.45 and any(hit.score > 0 for hit in hits)
        reason = (
            f"证据覆盖率为 {coverage:.0%}，可支持回答"
            if sufficient
            else f"证据仅覆盖问题要点的 {coverage:.0%}"
        )
        return EvidenceDecision(sufficient, reason, len(hits), missing[:8])

    def next_retrieval(
        self,
        question: str,
        previous_queries: tuple[str, ...],
        decision: EvidenceDecision,
        attempt: int,
        max_attempts: int,
    ) -> NextRetrieval:
        if decision.sufficient or attempt >= max_attempts:
            return NextRetrieval(False, "")
        missing = " ".join(decision.missing_information[:6])
        query = f"{question} {missing}".strip()
        if query in previous_queries:
            return NextRetrieval(False, "")
        return NextRetrieval(True, query)
