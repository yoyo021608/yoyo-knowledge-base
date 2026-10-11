import asyncio

from server.documents import DocumentsModule
from server.documents.types import SingleImportInput
from server.documents.worker import DocumentIndexWorker
from server.infra.database import Database


async def test_worker_processes_persisted_index_task(
    document_context: tuple[Database, DocumentsModule],
) -> None:
    """后台 Worker 只领取数据库任务，调用方无需保留进程内任务对象。"""
    _database, module = document_context
    imported = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="后台索引",
            content="文档保存后由后台执行索引。",
            source_type="note",
        )
    )
    assert imported.index_status == "queued"

    worker = DocumentIndexWorker(module.indexer, interval_seconds=0.01)
    worker.start()
    try:
        for _ in range(100):
            status = module.indexer.get_status(imported.document_id, "user-a")
            if status.status == "ready":
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("后台索引任务没有在预期时间内完成")
    finally:
        await worker.close()

    assert module.indexer.get_status(imported.document_id, "user-a").status == "ready"
