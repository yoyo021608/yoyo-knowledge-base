"""documents 模块内部装配。

应用入口只需要注入数据库；controller 与后续 agent 模块只接触这里公开的能力，
不会跨过边界直接访问 documents 数据表。
"""

from dataclasses import dataclass

from server.documents.documents import DocumentEditor
from server.documents.exporting import DocumentExporter
from server.documents.importing import BatchImporter, SingleImporter
from server.documents.indexing import DocumentIndexer
from server.documents.knowledge import DocumentKnowledge
from server.documents.organization import KnowledgeOrganization
from server.documents.search import DocumentSearch
from server.documents.sources import SourceManager
from server.infra.content import DocumentContentLoader
from server.infra.database import Database
from server.infra.embeddings import EmbeddingClient, FakeEmbeddingClient
from server.infra.files import LocalFileStorage


@dataclass(frozen=True, slots=True)
class DocumentsModule:
    """提供给 controller 和 Agent 工具适配层的 documents 公开能力集合。"""

    single_importer: SingleImporter
    batch_importer: BatchImporter
    editor: DocumentEditor
    organization: KnowledgeOrganization
    sources: SourceManager
    indexer: DocumentIndexer
    search: DocumentSearch
    knowledge: DocumentKnowledge
    exporter: DocumentExporter

    @classmethod
    def create(
        cls,
        database: Database,
        file_storage: LocalFileStorage | None = None,
        embeddings: EmbeddingClient | None = None,
        content_loader: DocumentContentLoader | None = None,
    ) -> "DocumentsModule":
        """用同一数据库装配互相协作但职责独立的文档能力。"""
        embedding_client = embeddings or FakeEmbeddingClient()
        indexer = DocumentIndexer(database, embedding_client)
        editor = DocumentEditor(database, indexer, file_storage)
        single_importer = SingleImporter(
            database, indexer, file_storage, content_loader
        )
        return cls(
            single_importer=single_importer,
            batch_importer=BatchImporter(database, single_importer),
            editor=editor,
            organization=KnowledgeOrganization(database),
            sources=SourceManager(database),
            indexer=indexer,
            search=DocumentSearch(database, embedding_client),
            knowledge=DocumentKnowledge(database),
            exporter=DocumentExporter(editor),
        )
