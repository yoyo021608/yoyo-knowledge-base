"""documents 的批量录入、索引和来源复查后台任务。"""

import asyncio
import logging
from contextlib import suppress

from redis.exceptions import RedisError

from server.documents.errors import DocumentNotFound
from server.documents.importing import BatchImporter
from server.documents.indexing import DocumentIndexer
from server.documents.source_changes import SourceChangeManager
from server.documents.types import RefreshRequest
from server.infra.jobs import Job, RedisJobQueue

_LOGGER = logging.getLogger(__name__)


class BatchImportWorker:
    """领取 documents 的持久化批次，重启后续跑尚未完成的条目。"""

    def __init__(self, importer: BatchImporter, interval_seconds: float = 2.0) -> None:
        self._importer = importer
        self._interval_seconds = interval_seconds
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="document-import-worker")

    async def close(self) -> None:
        self._stopped.set()
        if self._task is not None:
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await asyncio.to_thread(self._importer.run_queued)
            except Exception:
                _LOGGER.exception("documents.import_worker.scan_failed")
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval_seconds
                )
            except TimeoutError:
                continue


class DocumentIndexWorker:
    """将数据库待处理版本投递到 Redis；Redis 故障时直接扫描数据库。"""

    def __init__(
        self,
        indexer: DocumentIndexer,
        interval_seconds: float = 2.0,
        queue: RedisJobQueue | None = None,
    ) -> None:
        self._indexer = indexer
        self._interval_seconds = interval_seconds
        self._queue = queue
        self._queue_needs_recovery = queue is not None
        self._db_needs_recovery = False
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """启动单个后台循环，重复调用不会创建第二个消费者。"""
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="document-index-worker")

    async def close(self) -> None:
        """停止扫描并等待当前处理安全退出。"""
        self._stopped.set()
        if self._task is not None:
            # 等当前 to_thread 索引安全结束，避免数据库先于工作线程关闭。
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        try:
            await asyncio.to_thread(self._indexer.requeue_interrupted)
        except Exception:
            # 恢复扫描失败时，后续轮次继续找回 processing 任务。
            self._db_needs_recovery = True
            _LOGGER.exception("documents.index_worker.recovery_failed")
        while not self._stopped.is_set():
            try:
                if self._db_needs_recovery:
                    await asyncio.to_thread(self._indexer.requeue_interrupted)
                    self._db_needs_recovery = False
                if self._queue is None:
                    await asyncio.to_thread(self._indexer.refresh_queued)
                else:
                    await asyncio.to_thread(self._run_redis_cycle)
            except RedisError:
                self._queue_needs_recovery = True
                _LOGGER.warning(
                    "documents.index_worker.redis_unavailable", exc_info=True
                )
                try:
                    await asyncio.to_thread(self._indexer.refresh_queued)
                except Exception:
                    self._db_needs_recovery = True
                    _LOGGER.exception("documents.index_worker.scan_failed")
            except Exception:
                # 数据库恢复后重新领取中断的 processing；单轮故障不停止 Worker。
                self._db_needs_recovery = True
                self._queue_needs_recovery = self._queue is not None
                _LOGGER.exception("documents.index_worker.scan_failed")
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval_seconds
                )
            except TimeoutError:
                continue

    def _run_redis_cycle(self) -> None:
        """先消费旧通知；没有通知时才从数据库补投，避免重复排队。"""
        assert self._queue is not None
        if self._queue_needs_recovery:
            # 项目只运行一个执行进程，此时没有其他索引消费者。
            self._queue.requeue_interrupted()
            self._queue_needs_recovery = False

        job = self._queue.claim()
        if job is None:
            for request in self._indexer.queued_requests():
                self._queue.enqueue(
                    Job.create(
                        "document-index",
                        {
                            "document_id": request.document_id,
                            "version_id": request.version_id,
                        },
                    )
                )
            job = self._queue.claim()

        processed = 0
        while job is not None and processed < 100:
            document_id = job.payload.get("document_id")
            version_id = job.payload.get("version_id")
            if (
                job.kind != "document-index"
                or not isinstance(document_id, str)
                or not isinstance(version_id, str)
            ):
                _LOGGER.error("documents.index_worker.invalid_job job_id=%s", job.id)
            else:
                # 版本、权限和最终状态都由 documents 在数据库中重新核对。
                try:
                    self._indexer.refresh(RefreshRequest(document_id, version_id))
                except DocumentNotFound:
                    # 已删除文档的旧通知不应阻塞其他持久化任务。
                    _LOGGER.info("documents.index_worker.stale_job job_id=%s", job.id)
            self._queue.acknowledge(job)
            processed += 1
            if processed < 100:
                job = self._queue.claim()


class SourceWatchWorker:
    """低频检查网页来源，使用 documents 的版本规则发布变化。"""

    def __init__(
        self, changes: SourceChangeManager, interval_seconds: float = 3600
    ) -> None:
        self._changes = changes
        self._interval_seconds = interval_seconds
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="source-watch-worker")

    async def close(self) -> None:
        self._stopped.set()
        if self._task is not None:
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval_seconds
                )
                break
            except TimeoutError:
                pass
            try:
                await asyncio.to_thread(self._changes.check_due)
            except Exception:
                _LOGGER.exception("documents.source_watch.scan_failed")
