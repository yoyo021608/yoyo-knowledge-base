"""验证来源版本和增量索引不会破坏历史证据。"""

from pathlib import Path

import pytest

from server.documents import DocumentsModule
from server.documents.errors import DocumentNotFound
from server.documents.types import DocumentUpdateInput, SingleImportInput
from server.infra.content import ExtractedContent
from server.infra.database import Database
from server.infra.embeddings import FakeEmbeddingClient
from server.infra.files import LocalFileStorage


class ChangingWeb:
    content = "第一段资料。"

    def fetch_web(self, url: str) -> ExtractedContent:
        assert url == "https://example.com/knowledge"
        return ExtractedContent("网页标题", self.content)

    def extract_file(
        self, name: str, content: bytes, content_type: str
    ) -> ExtractedContent:
        raise AssertionError("网页复查不应解析文件")


class CountingEmbedding(FakeEmbeddingClient):
    cache_key = "test-counting-v1"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> tuple[float, ...]:
        self.calls.append(text)
        return super().embed(text)


def test_web_source_change_preserves_old_version_and_skips_unchanged(
    document_context: tuple[Database, DocumentsModule], tmp_path: Path
) -> None:
    database, _ = document_context
    web = ChangingWeb()
    module = DocumentsModule.create(
        database, LocalFileStorage(tmp_path / "web"), content_loader=web
    )
    imported = module.single_importer.import_web(
        user_id="user-a", source_url="https://example.com/knowledge"
    )
    assert module.source_changes.check_due() == 1
    assert module.source_changes.check_due() == 0
    assert not module.source_changes.check(imported.document_id, "user-a").changed
    assert len(module.editor.list_versions(imported.document_id, "user-a")) == 1
    with pytest.raises(DocumentNotFound):
        module.source_changes.check(imported.document_id, "user-b")

    web.content = "第一段资料。\n新增结论。"
    change = module.source_changes.check(imported.document_id, "user-a")
    assert change.changed
    assert "新增结论" in change.diff
    current = module.editor.get(imported.document_id, "user-a")
    assert current.document.source_changed_at is not None
    assert current.document.source_change_diff == change.diff
    assert (
        module.editor.get_version(
            imported.document_id, imported.version_id, "user-a"
        ).content_snapshot
        == "第一段资料。"
    )
    assert (
        module.editor.get(imported.document_id, "user-a").version.id
        == change.current_version_id
    )
    assert not module.source_changes.check(imported.document_id, "user-a").changed


def test_incremental_index_reuses_only_unchanged_chunks_with_same_model(
    document_context: tuple[Database, DocumentsModule], tmp_path: Path
) -> None:
    database, _ = document_context
    embeddings = CountingEmbedding()
    module = DocumentsModule.create(
        database, LocalFileStorage(tmp_path / "index"), embeddings=embeddings
    )
    original = "稳定的第一段。" + "甲" * 900 + "\n\n变化的第二段。"
    imported = module.single_importer.import_one(
        SingleImportInput(user_id="user-a", title="索引资料", content=original)
    )
    assert module.indexer.refresh_queued() == 1
    first_calls = len(embeddings.calls)
    assert first_calls >= 2
    module.editor.update(
        imported.document_id,
        "user-a",
        DocumentUpdateInput(
            title="索引资料", content=original.replace("变化的第二段", "更新的第二段")
        ),
    )
    assert module.indexer.refresh_queued() == 1
    assert len(embeddings.calls) < first_calls * 2
    assert len(module.editor.list_versions(imported.document_id, "user-a")) == 2
