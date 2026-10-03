"""按独立预算选择近期历史与证据，并执行最终输入上限检查。"""

from server.agent.errors import InputTooLong
from server.agent.prompts import ANSWER_SYSTEM_PROMPT
from server.agent.rag.text import take_tokens, token_count
from server.agent.types import (
    ContextInput,
    ContextPacket,
    MessageContext,
    SearchHitContext,
)

_MESSAGE_OVERHEAD = 4


def render_evidence(source: SearchHitContext, index: int) -> str:
    """统一证据输入格式，预算计算和模型调用必须使用同一文本。"""
    return f"【证据 {index}｜{source.title}】\n{source.content_snippet}"


class ContextAssembler:
    def build(
        self, input_value: ContextInput, system_prompt: str = ANSWER_SYSTEM_PROMPT
    ) -> ContextPacket:
        budget = input_value.budget
        available = (
            budget.model_window - budget.reserved_output_tokens - budget.safety_margin
        )
        fixed = (
            token_count(system_prompt)
            + token_count(input_value.question)
            + _MESSAGE_OVERHEAD
        )
        if available <= 0 or fixed > available:
            raise InputTooLong("系统指令和当前问题已经超过模型输入上限")

        selected_history: list[MessageContext] = []
        remaining_history = min(budget.history_budget, available - fixed)
        for message in reversed(input_value.history):
            size = token_count(message.content) + _MESSAGE_OVERHEAD
            if size <= remaining_history:
                selected_history.append(message)
                remaining_history -= size
        selected_history.reverse()

        used = fixed + sum(
            token_count(item.content) + _MESSAGE_OVERHEAD for item in selected_history
        )
        remaining_evidence = min(budget.evidence_budget, available - used)
        selected_sources: list[SearchHitContext] = []
        seen: set[tuple[str, str, str]] = set()
        for source in sorted(input_value.search_hits, key=lambda item: -item.score):
            key = (source.document_id, source.version_id, source.chunk_id)
            if key in seen or remaining_evidence <= 0:
                continue
            wrapper_cost = token_count(
                f"【证据 {len(selected_sources) + 1}｜{source.title}】\n"
            )
            snippet = take_tokens(
                source.content_snippet,
                max(0, remaining_evidence - wrapper_cost - _MESSAGE_OVERHEAD),
            )
            if not snippet:
                break
            selected_sources.append(
                SearchHitContext(
                    document_id=source.document_id,
                    version_id=source.version_id,
                    title=source.title,
                    content_snippet=snippet,
                    chunk_id=source.chunk_id,
                    source_url=source.source_url,
                    score=source.score,
                )
            )
            seen.add(key)
            remaining_evidence -= (
                token_count(
                    render_evidence(selected_sources[-1], len(selected_sources))
                )
                + _MESSAGE_OVERHEAD
            )

        messages = tuple(selected_history) + (
            MessageContext("user", input_value.question),
        )
        total = token_count(system_prompt) + sum(
            token_count(item.content) + _MESSAGE_OVERHEAD for item in messages
        )
        total += sum(
            token_count(render_evidence(item, index)) + _MESSAGE_OVERHEAD
            for index, item in enumerate(selected_sources, start=1)
        )
        if total > available:
            raise InputTooLong("组装后的模型输入超过上限")
        return ContextPacket(system_prompt, messages, tuple(selected_sources), total)
