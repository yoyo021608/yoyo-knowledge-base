"""评估候选、引用和证据状态，不改写知识或用户反馈。"""

from server.agent.types import AnswerResult, RunEvaluation, SearchHitContext


class RunEvaluator:
    def evaluate(
        self, hits: tuple[SearchHitContext, ...], answer: AnswerResult
    ) -> RunEvaluation:
        candidates = {
            (item.document_id, item.version_id, item.chunk_id) for item in hits
        }
        cited = {
            (item.document_id, item.document_version_id, item.chunk_id)
            for item in answer.citations
        }
        valid = len(candidates & cited)
        coverage = (1.0 if not hits else 0.0) if not cited else valid / len(cited)
        failure = None
        if answer.evidence_status == "sufficient" and not cited:
            failure = "回答没有标注任何证据"
        elif answer.evidence_status == "sufficient" and coverage < 1:
            failure = "部分引用不在本轮候选证据中"
        return RunEvaluation(
            hit_count=len(hits),
            citation_coverage=coverage,
            evidence_status=answer.evidence_status,
            failure_reason=failure,
        )
