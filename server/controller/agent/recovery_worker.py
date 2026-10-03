"""周期扫描可恢复 Run，不承载 Agent 或 sessions 的领域规则。"""

import asyncio
import logging
from contextlib import suppress

from server.agent.module import AgentModule
from server.controller.agent.recovery import recover_after_restart, recover_pending
from server.sessions.module import SessionsModule

_LOGGER = logging.getLogger(__name__)


class AgentRecoveryWorker:
    def __init__(
        self,
        agent: AgentModule,
        sessions: SessionsModule,
        interval_seconds: float,
        *,
        startup_recovered: bool = False,
    ) -> None:
        self._agent = agent
        self._sessions = sessions
        self._interval_seconds = interval_seconds
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._startup_recovered = startup_recovered

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="agent-recovery-worker")

    async def close(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                if not self._startup_recovered:
                    await asyncio.to_thread(
                        recover_after_restart, self._agent, self._sessions
                    )
                    self._startup_recovered = True
                else:
                    await asyncio.to_thread(
                        recover_pending, self._agent, self._sessions
                    )
            except Exception:
                _LOGGER.exception("agent.recovery.periodic_failed")
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval_seconds
                )
            except TimeoutError:
                continue
