import asyncio

import pytest
from fakeredis import FakeRedis
from redis.exceptions import RedisError

from server.documents import DocumentsModule
from server.documents.models import Document, DocumentIndexTask, DocumentVersion
from server.documents.types import SingleImportInput
from server.documents.worker import DocumentIndexWorker
from server.infra.database import Database
from server.infra.jobs import Job, RedisJobQueue


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

    redis = FakeRedis(decode_responses=True)
    queue = RedisJobQueue(redis, "test:document-index")
    queue.enqueue(
        Job.create(
            "document-index",
            {"document_id": "deleted-document", "version_id": "deleted-version"},
        )
    )
    worker = DocumentIndexWorker(module.indexer, interval_seconds=0.01, queue=queue)
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
    assert redis.llen("test:document-index:processing") == 0
    assert redis.llen("test:document-index") == 0


async def test_redis_outage_falls_back_to_persisted_index_tasks(
    document_context: tuple[Database, DocumentsModule], monkeypatch: pytest.MonkeyPatch
) -> None:
    _database, module = document_context
    imported = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="故障兜底",
            content="即使 Redis 暂时不可用，数据库中的任务仍能完成。",
            source_type="note",
        )
    )
    queue = RedisJobQueue(FakeRedis(decode_responses=True), "test:document-index")

    def unavailable() -> int:
        raise RedisError("redis unavailable")

    monkeypatch.setattr(queue, "requeue_interrupted", unavailable)
    worker = DocumentIndexWorker(module.indexer, interval_seconds=0.01, queue=queue)
    worker.start()
    try:
        for _ in range(100):
            if (
                module.indexer.get_status(imported.document_id, "user-a").status
                == "ready"
            ):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("Redis 故障时数据库任务没有完成")
    finally:
        await worker.close()


async def test_worker_recovers_interrupted_redis_claim(
    document_context: tuple[Database, DocumentsModule], monkeypatch: pytest.MonkeyPatch
) -> None:
    _database, module = document_context
    imported = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="重启恢复",
            content="索引通知中断后仍可继续。",
            source_type="note",
        )
    )
    redis = FakeRedis(decode_responses=True)
    queue = RedisJobQueue(redis, "test:document-index")
    queue.enqueue(
        Job.create(
            "document-index",
            {"document_id": imported.document_id, "version_id": imported.version_id},
        )
    )
    assert queue.claim() is not None
    with _database.transaction() as session:
        task = (
            session.query(DocumentIndexTask)
            .filter_by(document_id=imported.document_id, version_id=imported.version_id)
            .one()
        )
        task.status = "processing"
        document = session.get(Document, imported.document_id)
        version = session.get(DocumentVersion, imported.version_id)
        assert document is not None and version is not None
        document.index_status = "processing"
        version.index_status = "processing"

    original_recovery = module.indexer.requeue_interrupted
    attempts = 0

    def recover_after_one_failure() -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("database temporarily unavailable")
        return original_recovery()

    monkeypatch.setattr(
        module.indexer, "requeue_interrupted", recover_after_one_failure
    )

    worker = DocumentIndexWorker(module.indexer, interval_seconds=0.01, queue=queue)
    worker.start()
    try:
        for _ in range(200):
            if (
                module.indexer.get_status(imported.document_id, "user-a").status
                == "ready"
            ):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("中断的 Redis 通知没有恢复")
    finally:
        await worker.close()

    assert redis.llen("test:document-index:processing") == 0
    assert attempts >= 2


async def test_repeated_redis_notification_does_not_reindex_ready_version(
    document_context: tuple[Database, DocumentsModule],
) -> None:
    _database, module = document_context
    imported = module.single_importer.import_one(
        SingleImportInput(
            user_id="user-a",
            title="幂等索引",
            content="重复投递只处理一次。",
            source_type="note",
        )
    )
    redis = FakeRedis(decode_responses=True)
    queue = RedisJobQueue(redis, "test:document-index")
    notification = {
        "document_id": imported.document_id,
        "version_id": imported.version_id,
    }
    # 超过单轮 100 条上限时，最后一条必须留在队列而不是卡在 processing。
    for _ in range(101):
        queue.enqueue(Job.create("document-index", notification))
    worker = DocumentIndexWorker(module.indexer, interval_seconds=0.01, queue=queue)
    worker.start()
    try:
        for _ in range(100):
            if (
                module.indexer.get_status(imported.document_id, "user-a").status
                == "ready"
                and redis.llen("test:document-index") == 0
                and redis.llen("test:document-index:processing") == 0
            ):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("重复通知没有处理完成")
    finally:
        await worker.close()

    with _database.session() as session:
        task = (
            session.query(DocumentIndexTask)
            .filter_by(document_id=imported.document_id, version_id=imported.version_id)
            .one()
        )
        assert task.attempt_count == 1
