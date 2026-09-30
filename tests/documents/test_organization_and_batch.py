import pytest

from server.documents import DocumentsModule
from server.documents.errors import DocumentNotFound, TopicNotFound
from server.documents.types import (
    BatchImportInput,
    DocumentFilter,
    RelationInput,
    SingleImportInput,
    TopicInput,
)
from server.infra.database import Database


def test_topics_tags_favorites_and_relations_keep_ownership_boundaries(
    document_context: tuple[Database, DocumentsModule],
) -> None:
    _database, module = document_context
    topic = module.organization.create_topic(
        "user-a", TopicInput(name="研究", description="研究资料")
    )
    tag = module.organization.create_tag("user-a", "待复习")
    first = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="第一篇",
            content="事件总线用于模块间传递事件。",
            topic_id=topic.id,
        )
    )
    second = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a", title="第二篇", content="适配层连接模块公开端口。"
        )
    )

    module.organization.attach_tag(first.document_id, tag.id, "user-a")
    module.organization.set_favorite(first.document_id, "user-a", True)
    relation = module.organization.create_relation(
        RelationInput(
            user_id="user-a",
            source_document_id=first.document_id,
            target_document_id=second.document_id,
            relation_type="补充说明",
        )
    )
    assert len(module.organization.list_relations(first.document_id, "user-a")) == 1
    filtered = module.editor.list(
        "user-a", DocumentFilter(topic_id=topic.id, tag="待复习", is_favorite=True)
    )
    assert [document.id for document in filtered] == [first.document_id]

    with pytest.raises(DocumentNotFound):
        module.organization.list_relations(first.document_id, "user-b")
    with pytest.raises(DocumentNotFound):
        module.organization.attach_tag(first.document_id, tag.id, "user-b")

    module.organization.delete_relation(relation.id, "user-a")
    module.organization.delete_tag("user-a", tag.id)
    module.organization.delete_topic("user-a", topic.id)
    assert module.editor.get(first.document_id, "user-a").document.topic_id is None
    with pytest.raises(TopicNotFound):
        module.organization.delete_topic("user-a", topic.id)


def test_batch_failure_is_isolated_and_success_is_not_duplicated_on_retry(
    document_context: tuple[Database, DocumentsModule],
) -> None:
    _database, module = document_context
    result = module.batch_importer.create_job(
        BatchImportInput(
            user_id="user-a",
            items=(
                SingleImportInput(
                    user_id="ignored-user",
                    title="有效资料",
                    content="批量任务中的有效正文。",
                ),
                SingleImportInput(
                    user_id="ignored-user",
                    title="无网址网页",
                    content="该条目应失败。",
                    source_type="web",
                ),
            ),
        )
    )
    assert result.job.status == "partial"
    assert result.job.success_count == 1
    assert result.job.failure_count == 1
    successful_id = result.items[0].document_id

    retried = module.batch_importer.retry_failed(result.job.id, "user-a")
    assert retried.job.status == "partial"
    assert retried.items[0].document_id == successful_id
    assert len(module.editor.list("user-a", DocumentFilter())) == 1
    assert module.editor.list("ignored-user", DocumentFilter()) == ()

    module.editor.delete(successful_id or "", "user-a")
    after_delete = module.batch_importer.get_job(result.job.id, "user-a")
    assert after_delete.items[0].document_id is None
    assert after_delete.items[0].error_message == "原文已删除"
