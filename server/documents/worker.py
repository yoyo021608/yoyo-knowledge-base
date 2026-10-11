"""documents 的批量录入、索引和来源复查后台任务。"""

import asyncio
import logging
from contextlib import suppress

from server.documents.importing import BatchImporter
from server.documents.indexing import DocumentIndexer
from server.documents.source_changes import SourceChangeManager

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
    """周期处理 queued 任务，进程重启后仍以数据库状态为准。"""

    def __init__(self, indexer: DocumentIndexer, interval_seconds: float = 2.0) -> None:
        self._indexer = indexer
        self._interval_seconds = interval_seconds
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
            # 恢复扫描失败时保留数据库事实，随后正常轮询会继续重试 queued 任务。
            _LOGGER.exception("documents.index_worker.recovery_failed")
        while not self._stopped.is_set():
            try:
                await asyncio.to_thread(self._indexer.refresh_queued)
            except Exception:
                # 单轮基础设施故障不终止恢复循环；任务事实仍保存在数据库。
                _LOGGER.exception("documents.index_worker.scan_failed")
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval_seconds
                )
            except TimeoutError:
                continue


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
