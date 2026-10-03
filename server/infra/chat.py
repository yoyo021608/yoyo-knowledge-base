"""模型 SDK 的最薄接入层；提示词、证据和业务流程均留在 Agent。"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol, cast

from openai import OpenAI

from server.config import Settings

_LOGGER = logging.getLogger("yoyo.model")


@dataclass(frozen=True, slots=True)
class ChatInput:
    role: str
    content: str


class ChatClient(Protocol):
    def complete(
        self,
        system_prompt: str,
        messages: tuple[ChatInput, ...],
        max_output_tokens: int,
    ) -> str: ...


class FakeChatClient:
    """本地和测试使用的确定性模型替身，不伪造外部知识。"""

    def complete(
        self,
        system_prompt: str,
        messages: tuple[ChatInput, ...],
        max_output_tokens: int,
    ) -> str:
        del system_prompt, max_output_tokens
        evidence = [
            item.content for item in messages if item.content.startswith("【证据")
        ]
        if not evidence:
            return "当前知识库证据不足，无法给出可靠结论。"
        return "根据知识库资料：\n" + "\n".join(evidence[:3])


class OpenAIChatClient:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )
        self._model = settings.chat_model

    def complete(
        self,
        system_prompt: str,
        messages: tuple[ChatInput, ...],
        max_output_tokens: int,
    ) -> str:
        response: Any = self._client.responses.create(
            model=self._model,
            instructions=system_prompt,
            input=cast(
                Any,
                [{"role": item.role, "content": item.content} for item in messages],
            ),
            max_output_tokens=max_output_tokens,
        )
        text = cast(str, response.output_text).strip()
        if not text:
            raise RuntimeError("模型没有返回文本")
        return text


class TracedChatClient:
    """记录模型耗时和输入输出规模，不让追踪逻辑进入 Agent 业务层。"""

    def __init__(self, inner: ChatClient) -> None:
        self._inner = inner

    def complete(
        self,
        system_prompt: str,
        messages: tuple[ChatInput, ...],
        max_output_tokens: int,
    ) -> str:
        started = time.monotonic()
        input_chars = len(system_prompt) + sum(len(item.content) for item in messages)
        try:
            output = self._inner.complete(system_prompt, messages, max_output_tokens)
        except Exception:
            _LOGGER.exception(
                "model.complete.failed",
                extra={
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "input_chars": input_chars,
                    "message_count": len(messages),
                },
            )
            raise
        _LOGGER.info(
            "model.complete.succeeded",
            extra={
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "input_chars": input_chars,
                "output_chars": len(output),
                "message_count": len(messages),
            },
        )
        return output


def create_chat_client(settings: Settings) -> ChatClient:
    if settings.llm_provider == "fake":
        return TracedChatClient(FakeChatClient())
    return TracedChatClient(OpenAIChatClient(settings))
