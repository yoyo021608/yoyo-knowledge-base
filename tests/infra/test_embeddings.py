import logging
import math
from types import SimpleNamespace

import pytest

import server.infra.embeddings as embeddings
from server.config import Settings
from server.infra.embeddings import (
    EMBEDDING_DIMENSIONS,
    FakeEmbeddingClient,
    create_embedding_client,
)


def test_fake_embeddings_are_stable_normalized_and_fixed_size() -> None:
    """本地替身必须让索引和查询得到可复现且可比较的向量。"""
    client = FakeEmbeddingClient()
    first = client.embed("混合检索 vector search")
    second = client.embed("混合检索 vector search")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_fake_provider_assembles_fake_embedding_client() -> None:
    settings = Settings(_env_file=None, llm_provider="fake")
    assert isinstance(create_embedding_client(settings), FakeEmbeddingClient)


def test_real_embedding_uses_configured_timeout_and_retry_budget(
    monkeypatch,
) -> None:
    options: dict[str, object] = {}

    def fake_openai(**kwargs: object) -> object:
        options.update(kwargs)
        return object()

    monkeypatch.setattr(embeddings, "OpenAI", fake_openai)
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="test-key",
        openai_timeout_seconds=12.5,
        openai_max_retries=1,
    )

    create_embedding_client(settings)

    assert options["timeout"] == 12.5
    assert options["max_retries"] == 1


def test_real_embedding_logs_reported_tokens_without_source_text(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0] * EMBEDDING_DIMENSIONS)],
        usage=SimpleNamespace(prompt_tokens=6, total_tokens=6),
    )
    sdk = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **_kwargs: response))
    monkeypatch.setattr(embeddings, "OpenAI", lambda **_kwargs: sdk)
    settings = Settings(
        _env_file=None, llm_provider="openai", openai_api_key="test-key"
    )
    client = create_embedding_client(settings)

    with caplog.at_level(logging.INFO, logger="yoyo.model"):
        values = client.embed("私人文档正文")

    assert len(values) == EMBEDDING_DIMENSIONS
    trace = next(
        record for record in caplog.records if record.msg == "embedding.succeeded"
    )
    assert trace.input_tokens == 6
    assert trace.total_tokens == 6
    assert "私人文档正文" not in caplog.text
