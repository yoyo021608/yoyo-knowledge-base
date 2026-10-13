"""Embedding SDK 连接与可复现的本地替身。

infra 只负责把文本转换成固定维度向量，不决定文档如何切分、何时检索或如何排序。
"""

import hashlib
import logging
import math
import re
import time
from collections.abc import Sequence
from typing import Protocol

from openai import OpenAI

from server.config import Settings
from server.infra.tracing import current_run_id

EMBEDDING_DIMENSIONS = 256
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_+#.-]+|[\u3400-\u9fff]")
_LOGGER = logging.getLogger("yoyo.model")


class EmbeddingClient(Protocol):
    """documents 和 agent 可注入使用的最小向量能力。"""

    def embed(self, text: str) -> tuple[float, ...]:
        """把一段文本转换成固定维度的归一化向量。"""


class FakeEmbeddingClient:
    """为本地开发和测试生成稳定向量，不调用外部服务。"""

    cache_key = "fake-sha256-256-v1"

    def embed(self, text: str) -> tuple[float, ...]:
        values = [0.0] * EMBEDDING_DIMENSIONS
        tokens = _TOKEN_PATTERN.findall(text.casefold())
        # 中文字符同时加入相邻双字特征，使短语相近度比单字重合更可靠。
        chinese = "".join(token for token in tokens if "\u3400" <= token <= "\u9fff")
        tokens.extend(chinese[index : index + 2] for index in range(len(chinese) - 1))
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] & 1 else -1.0
            values[index] += sign
        magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
        return tuple(value / magnitude for value in values)


class OpenAIEmbeddingClient:
    """直接使用 OpenAI 兼容 SDK 获取文档和查询向量。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._model = model
        self.cache_key = (
            "openai:"
            + hashlib.sha256(
                f"{base_url.rstrip('/')}:{model}:{EMBEDDING_DIMENSIONS}".encode()
            ).hexdigest()
        )

    def embed(self, text: str) -> tuple[float, ...]:
        started = time.monotonic()
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=EMBEDDING_DIMENSIONS,
            )
            values: Sequence[float] = response.data[0].embedding
            if len(values) != EMBEDDING_DIMENSIONS:
                raise RuntimeError("Embedding 服务返回了错误的向量维度")
            result = tuple(float(value) for value in values)
        except Exception:
            _LOGGER.exception(
                "embedding.failed run_id=%s model=%s duration_ms=%.2f",
                current_run_id() or "-",
                self._model,
                (time.monotonic() - started) * 1000,
                extra={
                    "run_id": current_run_id(),
                    "model": self._model,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "input_chars": len(text),
                },
            )
            raise
        usage = getattr(response, "usage", None)
        _LOGGER.info(
            "embedding.succeeded run_id=%s model=%s input_tokens=%s total_tokens=%s",
            current_run_id() or "-",
            self._model,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "total_tokens", None),
            extra={
                "run_id": current_run_id(),
                "model": self._model,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "input_chars": len(text),
                "input_tokens": getattr(usage, "prompt_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            },
        )
        return result


def create_embedding_client(settings: Settings) -> EmbeddingClient:
    """按运行配置创建一个明确的 SDK 连接或本地替身。"""
    if settings.llm_provider == "openai":
        return OpenAIEmbeddingClient(
            settings.openai_api_key,
            settings.openai_base_url,
            settings.embedding_model,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )
    return FakeEmbeddingClient()
