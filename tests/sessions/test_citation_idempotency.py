from server.infra.database import Database
from server.sessions import SessionsModule
from server.sessions.types import CitationInput


def test_multiple_citations_keep_order_across_retry(
    sessions_context: tuple[Database, SessionsModule],
) -> None:
    """引用重放顺序由显式位置决定，不能依赖随机 UUID 排序。"""
    _, module = sessions_context
    conversation = module.management.create("user-a")
    module.management.try_claim_run(conversation.id, "user-a", "run-ordered")
    citations = (
        CitationInput("doc-1", "version-1", "chunk-1", "第一份", "证据一"),
        CitationInput("doc-2", "version-2", "chunk-2", "第二份", "证据二"),
    )
    first = module.history.save_answer(
        conversation.id, "user-a", "run-ordered", "回答", citations
    )
    retried = module.history.save_answer(
        conversation.id, "user-a", "run-ordered", "回答", citations
    )
    assert [item.document_id for item in first.citations] == ["doc-1", "doc-2"]
    assert [item.document_id for item in retried.citations] == ["doc-1", "doc-2"]
