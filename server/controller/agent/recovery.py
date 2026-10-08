"""不依赖 HTTP 的跨模块恢复协调，供启动入口和后台扫描复用。"""

import logging

from server.agent.errors import AgentError, AgentRunNotFound
from server.agent.module import AgentModule
from server.controller.agent.coordination import (
    output_from_snapshot,
    persist_final_result,
)
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule

_LOGGER = logging.getLogger(__name__)


def recover_pending(agent: AgentModule, sessions: SessionsModule) -> int:
    """重试最终保存，并补偿终态关联和两阶段会话删除。"""
    recovered = 0
    for run in agent.runs.list_recoverable():
        if run.status != "finalizing":
            continue
        try:
            sessions.management.get(run.session_id, run.user_id)
            # 上次异常若已经释放关联，恢复协调可重新领取同一个 Run。
            sessions.management.try_claim_run(run.session_id, run.user_id, run.id)
            output = output_from_snapshot(agent, run.id, run.user_id)
            snapshot = agent.runs.get(run.id, run.user_id).snapshot
            persist_final_result(
                sessions,
                session_id=run.session_id,
                user_id=run.user_id,
                run_id=run.id,
                mode=run.mode,
                question=snapshot.input.question,
                output=output,
            )
            agent.runs.complete(run.id, run.user_id)
            sessions.management.release_run(run.session_id, run.user_id, run.id)
            recovered += 1
        except (AgentError, SessionsError, RuntimeError):
            _LOGGER.warning(
                "agent.finalization.recovery_failed",
                extra={"run_id": run.id},
                exc_info=True,
            )
            continue

    # 处理 Complete/Fail/Cancel 已提交，但 release_run 前进程中断的情况。
    for session in sessions.management.list_claimed():
        run_id = session.active_run_id
        if run_id is None:
            continue
        missing = False
        try:
            status = agent.runs.get(run_id, session.user_id).run.status
        except AgentRunNotFound:
            missing = True
            status = "failed"
        if missing or status in {"completed", "failed", "cancelled"}:
            sessions.management.release_run(session.id, session.user_id, run_id)
            recovered += 1

    # deleting 会话不再接受新任务，可安全重试“清 Run → 释放 → 删会话”。
    for session in sessions.management.list_deleting():
        try:
            agent.runs.purge_session_runs(session.id, session.user_id)
            if session.active_run_id is not None:
                sessions.management.release_run(
                    session.id, session.user_id, session.active_run_id
                )
            sessions.management.delete(session.id, session.user_id)
            recovered += 1
        except (AgentError, SessionsError):
            _LOGGER.warning(
                "session.deletion.recovery_failed",
                extra={"session_id": session.id},
                exc_info=True,
            )
            continue
    return recovered


def recover_after_restart(agent: AgentModule, sessions: SessionsModule) -> int:
    """启动时暂停失去执行者的 Run，清理孤立 queued，并补偿最终保存。"""
    paused = 0
    cleaned = 0
    for run in agent.runs.list_recoverable():
        if run.status == "running":
            agent.runs.pause_interrupted(run.id)
            paused += 1
            continue
        if run.status != "queued":
            continue
        try:
            session = sessions.management.get(run.session_id, run.user_id)
            if session.active_run_id != run.id:
                agent.runs.fail(run.id, run.user_id, "运行未能领取所属会话")
                cleaned += 1
            else:
                agent.runs.pause_interrupted(run.id)
                paused += 1
        except SessionsError:
            agent.runs.fail(run.id, run.user_id, "所属会话不存在")
            cleaned += 1
    return paused + cleaned + recover_pending(agent, sessions)
