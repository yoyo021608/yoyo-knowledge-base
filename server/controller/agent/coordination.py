"""不依赖 HTTP 的 Agent 跨模块协调，供路由和恢复任务共同调用。"""

import logging
from dataclasses import dataclass, replace

from server.agent.errors import AgentError, AgentRunConflict
from server.agent.evaluation import RunEvaluator
from server.agent.module import AgentModule
from server.agent.types import (
    AgentMode,
    ContextInput,
    ExecutionOptions,
    MessageContext,
    RunBundle,
    WorkflowOutput,
)
from server.sessions.errors import SessionsError
from server.sessions.module import SessionsModule
from server.sessions.types import CitationInput, MessageView

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QuestionCommand:
    session_id: str
    request_id: str
    question: str
    mode: AgentMode
    topic_id: str | None = None
    tag: str | None = None
    document_ids: tuple[str, ...] = ()
    version_ids: tuple[str, ...] = ()
    user_answer: str | None = None


@dataclass(frozen=True, slots=True)
class QuestionOutcome:
    run_id: str
    status: str
    message: MessageView | None
    output: WorkflowOutput


@dataclass(frozen=True, slots=True)
class PreparedQuestion:
    """HTTP 接收阶段的持久化结果；只有 queued 运行需要交给后台执行。"""

    bundle: RunBundle
    should_execute: bool


def _history(
    sessions: SessionsModule, session_id: str, user_id: str
) -> tuple[MessageContext, ...]:
    return tuple(
        MessageContext(value.role, value.content)
        for value in sessions.history.list(session_id, user_id)
    )


def output_from_snapshot(
    agent: AgentModule, run_id: str, user_id: str
) -> WorkflowOutput:
    snapshot = agent.runs.get(run_id, user_id).snapshot
    if snapshot.result is None:
        raise RuntimeError("最终提交阶段缺少完整回答快照")
    evaluation = RunEvaluator().evaluate(snapshot.selected_sources, snapshot.result)
    return WorkflowOutput(snapshot.result, evaluation, snapshot.mode_result)


def persist_final_result(
    sessions: SessionsModule,
    *,
    session_id: str,
    user_id: str,
    run_id: str,
    mode: AgentMode,
    question: str,
    output: WorkflowOutput,
) -> MessageView:
    """按 Run 幂等保存回答，以及对应模式的 sessions 结果。"""
    citations = tuple(
        CitationInput(
            document_id=value.document_id,
            document_version_id=value.document_version_id,
            chunk_id=value.chunk_id,
            title_snapshot=value.title_snapshot,
            quote=value.quote,
            source_url=value.source_url,
        )
        for value in output.answer.citations
    )
    message = sessions.history.save_answer(
        session_id, user_id, run_id, output.answer.text, citations
    )
    mode_result = output.mode_result or {}
    if mode in {"research", "comparison"}:
        sessions.results.save_task(
            session_id,
            user_id,
            run_id,
            mode,
            question,
            "completed",
            mode_result,
        )
    elif mode == "study" and "user_answer" in mode_result:
        sessions.results.save_practice(
            session_id,
            user_id,
            run_id,
            question,
            str(mode_result["user_answer"]),
            str(mode_result.get("verdict", "insufficient_evidence")),
            str(mode_result.get("explanation", output.answer.text)),
            mode_result.get("mastery", {}),
        )
    return message


def _cleanup_failure(
    agent: AgentModule,
    sessions: SessionsModule,
    command: QuestionCommand,
    user_id: str,
    run_id: str,
    claimed: bool,
    reason: str,
) -> None:
    if not run_id:
        return
    try:
        status = agent.runs.get(run_id, user_id).run.status
    except AgentError:
        status = None
    # finalizing 必须保留领取关系，恢复任务才能幂等完成 sessions 写入。
    if status not in {"finalizing", "completed", "cancelled", "failed"}:
        try:
            agent.runs.fail(run_id, user_id, reason)
            status = "failed"
        except AgentError:
            _LOGGER.warning(
                "agent.run.cleanup_failed",
                extra={"run_id": run_id},
                exc_info=True,
            )
    if claimed and status not in {"finalizing", "running"}:
        sessions.management.release_run(command.session_id, user_id, run_id)


def prepare_question(
    agent: AgentModule,
    sessions: SessionsModule,
    user_id: str,
    command: QuestionCommand,
) -> PreparedQuestion:
    """持久化 Run、原始参数和用户消息，随后即可向客户端返回 run_id。"""
    sessions.management.get(command.session_id, user_id)
    options = ExecutionOptions(
        topic_id=command.topic_id,
        tag=command.tag,
        document_ids=command.document_ids,
        version_ids=command.version_ids,
        user_answer=command.user_answer,
    )
    context = ContextInput(
        question=command.question,
        history=_history(sessions, command.session_id, user_id),
        search_hits=(),
        budget=agent.default_budget,
    )
    bundle = agent.runs.create_run(
        command.session_id,
        user_id,
        command.request_id,
        command.mode,
        context,
        options,
    )
    if bundle.run.status in {"cancelled", "failed"}:
        raise AgentRunConflict("终态运行不能用原 request_id 重新执行")
    if bundle.run.status != "queued":
        return PreparedQuestion(bundle, False)

    claimed = False
    try:
        sessions.management.try_claim_run(command.session_id, user_id, bundle.run.id)
        claimed = True
        sessions.history.append_user(
            command.session_id, user_id, bundle.run.id, command.question
        )
    except (AgentError, SessionsError) as exc:
        _cleanup_failure(
            agent,
            sessions,
            command,
            user_id,
            bundle.run.id,
            claimed,
            str(exc),
        )
        raise
    return PreparedQuestion(agent.runs.get(bundle.run.id, user_id), True)


def _command_from_bundle(bundle: RunBundle) -> QuestionCommand:
    options = bundle.snapshot.options
    return QuestionCommand(
        session_id=bundle.run.session_id,
        request_id=bundle.run.request_id,
        question=bundle.snapshot.input.question,
        mode=bundle.run.mode,
        topic_id=options.topic_id,
        tag=options.tag,
        document_ids=options.document_ids,
        version_ids=options.version_ids,
        user_answer=options.user_answer,
    )


def execute_prepared_question(
    agent: AgentModule,
    sessions: SessionsModule,
    user_id: str,
    run_id: str,
) -> QuestionOutcome:
    """执行已持久化的 Run；恢复时完全使用服务端快照中的原始参数。"""
    claimed = True
    bundle = agent.runs.get(run_id, user_id)
    command = _command_from_bundle(bundle)
    try:
        if bundle.run.status == "completed":
            output = output_from_snapshot(agent, run_id, user_id)
            message = next(
                (
                    value
                    for value in sessions.history.list(command.session_id, user_id)
                    if value.run_id == run_id and value.role == "assistant"
                ),
                None,
            )
            return QuestionOutcome(run_id, "completed", message, output)
        if bundle.run.status in {"cancelled", "failed"}:
            raise AgentRunConflict("终态运行不能重新执行")

        sessions.management.try_claim_run(command.session_id, user_id, run_id)
        user_message = sessions.history.append_user(
            command.session_id, user_id, run_id, command.question
        )
        if bundle.run.status == "finalizing":
            output = output_from_snapshot(agent, run_id, user_id)
        else:
            if bundle.run.status == "paused":
                agent.runs.continue_run(run_id, user_id)
            executing = agent.runs.execute_run(run_id, user_id, user_message.id)
            output = agent.workflows.execute(
                executing, user_id, executing.snapshot.options
            )
            generated = agent.runs.get(run_id, user_id).snapshot
            agent.runs.save_snapshot(
                replace(generated, step="persist_answer"),
                generated.revision,
                "answer.ready",
            )
            agent.runs.begin_finalize(run_id, user_id)

        answer_message = persist_final_result(
            sessions,
            session_id=command.session_id,
            user_id=user_id,
            run_id=run_id,
            mode=command.mode,
            question=command.question,
            output=output,
        )
        completed = agent.runs.complete(run_id, user_id)
        sessions.management.release_run(command.session_id, user_id, run_id)
        claimed = False
        return QuestionOutcome(run_id, completed.status, answer_message, output)
    except (AgentError, SessionsError) as exc:
        _cleanup_failure(agent, sessions, command, user_id, run_id, claimed, str(exc))
        raise
    except Exception:
        _LOGGER.exception("agent.question.unexpected_failure", extra={"run_id": run_id})
        _cleanup_failure(
            agent,
            sessions,
            command,
            user_id,
            run_id,
            claimed,
            "执行过程中发生未预期错误",
        )
        raise


def execute_prepared_in_background(
    agent: AgentModule,
    sessions: SessionsModule,
    user_id: str,
    run_id: str,
) -> None:
    """后台任务边界统一吸收已记录的异常，避免响应发送后异常泄漏到 ASGI。"""
    try:
        execute_prepared_question(agent, sessions, user_id, run_id)
    except (AgentError, SessionsError):
        _LOGGER.warning(
            "agent.question.background_failed",
            extra={"run_id": run_id},
            exc_info=True,
        )
    except Exception:
        # execute_prepared_question 已记录上下文和失败状态，这里只隔离后台边界。
        pass


def execute_question(
    agent: AgentModule,
    sessions: SessionsModule,
    user_id: str,
    command: QuestionCommand,
) -> QuestionOutcome:
    """同步适配器保留给模块测试；HTTP 路由使用 prepare + 后台执行。"""
    prepared = prepare_question(agent, sessions, user_id, command)
    return execute_prepared_question(agent, sessions, user_id, prepared.bundle.run.id)


def cancel_and_release(
    agent: AgentModule,
    sessions: SessionsModule,
    run_id: str,
    user_id: str,
) -> None:
    run = agent.runs.cancel(run_id, user_id)
    sessions.management.release_run(run.session_id, user_id, run.id)
