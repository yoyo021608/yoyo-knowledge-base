from pathlib import Path

import pytest
from sqlalchemy import select

from server.documents import DocumentsModule
from server.documents.errors import DocumentNotFound
from server.documents.models import (
    DocumentIndexTask,
    KnowledgeEntity,
    KnowledgePoint,
    KnowledgeRelation,
)
from server.documents.types import (
    DocumentFilter,
    DocumentUpdateInput,
    ExportRequest,
    RefreshRequest,
    SearchQuery,
    SingleImportInput,
    StoredFileInput,
)
from server.infra.content import ExtractedContent
from server.infra.database import Database
from server.infra.files import FileNotFoundInStorageError, LocalFileStorage


class StubContentLoader:
    """测试中隔离真实网络和办公文件解析。"""

    def fetch_web(self, url: str) -> ExtractedContent:
        assert url == "https://example.com/knowledge"
        return ExtractedContent("网页标题", "- [[RAG]] 使用 `pgvector` 检索。")

    def extract_file(
        self, name: str, content: bytes, content_type: str
    ) -> ExtractedContent:
        del content, content_type
        return ExtractedContent(name, "文件正文")


class FailingEmbeddingClient:
    """模拟外部 Embedding 故障，验证版本不会因索引失败而丢失。"""

    def embed(self, text: str) -> tuple[float, ...]:
        del text
        raise RuntimeError("embedding unavailable")


def test_import_update_search_archive_restore_and_export(
    document_context: tuple[Database, DocumentsModule],
) -> None:
    database, module = document_context
    imported = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="RAG 设计笔记",
            content=(
                "- [[RAGFlow]] 使用 `pgvector` 组合关键词和向量候选。\n\n"
                "引用必须绑定文档版本。"
            ),
            source_type="markdown",
            source_url="https://example.com/rag",
            tags=("RAG", "架构"),
        )
    )

    detail = module.editor.get(imported.document_id, "user-a")
    assert detail.document.index_status == "ready"
    assert detail.document.tags == ("RAG", "架构")
    assert detail.version.source.source_url == "https://example.com/rag"
    assert module.search.search(
        SearchQuery(user_id="user-a", text="混合检索", mode="hybrid")
    )
    assert not module.search.search(
        SearchQuery(user_id="user-b", text="混合检索", mode="hybrid")
    )

    old_version_id = detail.version.id
    updated = module.editor.update(
        imported.document_id,
        "user-a",
        DocumentUpdateInput(
            title="RAG 设计笔记 v2",
            content="新版本中 [[RAGFlow]] 使用 `pgvector`、倒排索引、向量召回和来源复核。",
            tags=("RAG",),
            source_url="https://example.com/rag-v2",
        ),
    )
    assert updated.version == 2
    assert (
        "RAGFlow"
        in module.editor.get_version(
            imported.document_id, old_version_id, "user-a"
        ).content_snapshot
    )
    assert len(module.editor.list_versions(imported.document_id, "user-a")) == 2

    # 延迟到达的旧版本任务不会覆盖当前版本或把旧正文重新放回候选。
    module.indexer.refresh(
        RefreshRequest(document_id=imported.document_id, version_id=old_version_id)
    )
    current = module.editor.get(imported.document_id, "user-a")
    assert current.version.id == updated.id
    assert not module.search.search(
        SearchQuery(user_id="user-a", text="引用必须绑定", mode="full_text")
    )
    # 普通问答不读取旧索引；版本对比显式指定时仍可检索历史快照。
    historical = module.search.search(
        SearchQuery(
            user_id="user-a",
            text="引用必须绑定",
            mode="full_text",
            version_ids=(old_version_id,),
        )
    )
    assert {item.version_id for item in historical} == {old_version_id}
    assert module.search.validate_sources(
        "user-a", historical, allow_historical_versions=True
    )
    assert not module.search.validate_sources("user-a", historical)
    assert module.search.search(
        SearchQuery(user_id="user-a", text="向量召回", mode="hybrid")
    )
    with database.session() as session:
        tasks = session.scalars(
            select(DocumentIndexTask).where(
                DocumentIndexTask.document_id == imported.document_id
            )
        ).all()
        assert {task.status for task in tasks} == {"completed"}
        assert session.scalars(
            select(KnowledgePoint).where(
                KnowledgePoint.document_id == imported.document_id
            )
        ).all()

        assert {
            entity.name
            for entity in session.scalars(
                select(KnowledgeEntity).where(KnowledgeEntity.user_id == "user-a")
            ).all()
        } >= {"RAGFlow", "pgvector"}
        assert session.scalars(
            select(KnowledgeRelation).where(
                KnowledgeRelation.document_id == imported.document_id
            )
        ).all()

    knowledge = module.knowledge.get(imported.document_id, "user-a")
    assert knowledge.version_id == updated.id
    assert {entity.name for entity in knowledge.entities} >= {"RAGFlow", "pgvector"}
    assert knowledge.points
    assert knowledge.relations

    module.editor.archive(imported.document_id, "user-a")
    assert module.editor.list("user-a", DocumentFilter()) == ()
    assert not module.search.search(
        SearchQuery(user_id="user-a", text="向量召回", mode="hybrid")
    )
    module.editor.restore(imported.document_id, "user-a")
    assert len(module.editor.list("user-a", DocumentFilter())) == 1

    exported = module.exporter.export(ExportRequest(user_id="user-a", format="json"))
    assert exported.file_name == "knowledge-base.json"
    assert "RAG 设计笔记 v2" in exported.content.decode("utf-8")


def test_file_is_removed_with_deleted_document(
    document_context: tuple[Database, DocumentsModule], tmp_path: Path
) -> None:
    _database, module = document_context
    imported = module.single_importer.import_file(
        StoredFileInput(
            user_id="user-a",
            name="notes.md",
            content="# 上传文件\n\n文件内容可检索。".encode(),
            content_type="text/markdown",
        )
    )
    source = module.editor.get(imported.document_id, "user-a").version.source
    assert source.source_type == "file"

    # 从磁盘找到唯一文件标识，确认删除不仅清理数据库正文。
    metadata_files = list((tmp_path / "uploads").glob("*.json"))
    assert len(metadata_files) == 1
    file_id = metadata_files[0].stem
    module.editor.delete(imported.document_id, "user-a")
    with pytest.raises(DocumentNotFound):
        module.editor.get(imported.document_id, "user-a")
    with pytest.raises(FileNotFoundInStorageError):
        LocalFileStorage(tmp_path / "uploads").get(file_id)


def test_web_import_can_fetch_content_from_url(
    document_context: tuple[Database, DocumentsModule], tmp_path: Path
) -> None:
    """网页只提供 URL 时由注入的 infra 端口取得正文和来源标题。"""
    database, _original = document_context
    module = DocumentsModule.create(
        database,
        LocalFileStorage(tmp_path / "web-uploads"),
        content_loader=StubContentLoader(),
    )
    result = module.single_importer.import_web(
        user_id="user-a", source_url="https://example.com/knowledge"
    )
    detail = module.editor.get(result.document_id, "user-a")
    assert detail.document.title == "网页标题"
    assert detail.version.source.source_url == "https://example.com/knowledge"
    assert detail.version.source.content.startswith("- [[RAG]]")
    module.editor.delete(result.document_id, "user-a")


def test_update_keeps_failed_version_for_explicit_index_retry(
    document_context: tuple[Database, DocumentsModule], tmp_path: Path
) -> None:
    """编辑已提交后索引失败应返回 failed 版本，不能让用户误以为内容未保存。"""
    database, module = document_context
    imported = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="原始版本",
            content="原始内容可以正常建立索引。",
            source_type="note",
        )
    )
    failing_module = DocumentsModule.create(
        database,
        LocalFileStorage(tmp_path / "failed-update-uploads"),
        embeddings=FailingEmbeddingClient(),
    )

    updated = failing_module.editor.update(
        imported.document_id,
        "user-a",
        DocumentUpdateInput(title="已保存的新版本", content="等待重新建立索引。"),
    )

    assert updated.version == 2
    assert updated.index_status == "failed"
    assert "embedding unavailable" in (updated.index_error or "")
    assert (
        failing_module.editor.get(imported.document_id, "user-a").version.id
        == updated.id
    )
