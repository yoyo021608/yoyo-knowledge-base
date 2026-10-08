"""持久化索引任务的后台恢复扫描。"""

import asyncio
import logging
from contextlib import suppress

from server.documents.indexing import DocumentIndexer

_LOGGER = logging.getLogger(__name__)


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
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
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
