import pytest

from server.infra.database import Database
from server.sessions import SessionsModule
from server.sessions.errors import (
    IdempotencyConflict,
    InvalidSessionInput,
    SessionBusy,
    SessionDeleting,
    SessionNotFound,
)
from server.sessions.types import CitationInput


def test_session_run_and_history_are_owned_and_idempotent(
    sessions_context: tuple[Database, SessionsModule],
) -> None:
    _, module = sessions_context
    conversation = module.management.create("user-a", "论文调研")
    module.management.try_claim_run(conversation.id, "user-a", "run-1")
    user_message = module.history.append_user(
        conversation.id, "user-a", "run-1", "结论是什么？"
    )
    assert (
        module.history.append_user(
            conversation.id, "user-a", "run-1", "结论是什么？"
        ).id
        == user_message.id
    )
    with pytest.raises(IdempotencyConflict):
        module.history.append_user(conversation.id, "user-a", "run-1", "换一个问题")
    with pytest.raises(SessionBusy):
        module.management.try_claim_run(conversation.id, "user-a", "run-2")
    with pytest.raises(SessionNotFound):
        module.management.get(conversation.id, "user-b")


def test_answer_keeps_citation_snapshot_and_delete_blocks_late_writes(
    sessions_context: tuple[Database, SessionsModule],
) -> None:
    _, module = sessions_context
    conversation = module.management.create("user-a")
    module.management.try_claim_run(conversation.id, "user-a", "run-1")
    answer = module.history.save_answer(
        conversation.id,
        "user-a",
        "run-1",
        "这是答案",
        (
            CitationInput(
                document_id="doc",
                document_version_id="version",
                chunk_id="chunk",
                title_snapshot="旧标题",
                quote="证据原文",
                source_url="https://example.com",
            ),
        ),
    )
    assert answer.citations[0].quote == "证据原文"
    with pytest.raises(InvalidSessionInput):
        module.history.save_answer(
            conversation.id,
            "user-a",
            "run-other",
            "无效引用",
            (CitationInput("", "version", "chunk", "标题", "摘录"),),
        )
    module.management.begin_delete(conversation.id, "user-a")
    with pytest.raises(SessionDeleting):
        module.history.append_user(conversation.id, "user-a", "run-1", "迟到消息")
    module.management.release_run(conversation.id, "user-a", "run-1")
    module.management.delete(conversation.id, "user-a")
    module.management.delete(conversation.id, "user-a")
    with pytest.raises(SessionNotFound):
        module.management.get(conversation.id, "user-a")


def test_results_practice_and_feedback_remain_sessions_responsibility(
    sessions_context: tuple[Database, SessionsModule],
) -> None:
    _, module = sessions_context
    conversation = module.management.create("user-a")
    module.management.try_claim_run(conversation.id, "user-a", "run-1")
    message = module.history.save_answer(conversation.id, "user-a", "run-1", "报告完成")
    task = module.results.save_task(
        conversation.id,
        "user-a",
        "run-1",
        "research",
        "研究问题",
        "completed",
        {"report": "结果"},
    )
    module.management.release_run(conversation.id, "user-a", "run-1")
    retried_task = module.results.save_task(
        conversation.id,
        "user-a",
        "run-1",
        "research",
        "研究问题",
        "completed",
        {"report": "结果"},
    )
    module.management.try_claim_run(conversation.id, "user-a", "run-2")
    practice = module.results.save_practice(
        conversation.id,
        "user-a",
        "run-2",
        "问题",
        "答案",
        "correct",
        "解析",
        {"topic": 0.8},
    )
    retried_practice = module.results.save_practice(
        conversation.id,
        "user-a",
        "run-2",
        "问题",
        "答案",
        "correct",
        "解析",
        {"topic": 0.8},
    )
    module.management.release_run(conversation.id, "user-a", "run-2")
    released_retry = module.results.save_practice(
        conversation.id,
        "user-a",
        "run-2",
        "问题",
        "答案",
        "correct",
        "解析",
        {"topic": 0.8},
    )
    feedback = module.results.save_feedback(
        conversation.id, "user-a", "message", message.id, 1, "有帮助"
    )
    assert task.result_json == '{"report":"结果"}'
    assert retried_task.id == task.id
    assert practice.mastery_snapshot_json == '{"topic":0.8}'
    assert retried_practice.id == practice.id
    assert released_retry.id == practice.id
    assert feedback.rating == 1
