"""模型连接只记录技术调用事实，不记录用户正文。"""

import logging
from types import SimpleNamespace

import pytest

import server.infra.chat as chat_module
from server.config import Settings
from server.infra.chat import ChatInput, OpenAIChatClient, TracedChatClient
from server.infra.tracing import current_run_id, trace_run


def test_real_chat_logs_reported_tokens_without_prompt_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    response = SimpleNamespace(
        output_text="可以回答",
        usage=SimpleNamespace(input_tokens=17, output_tokens=4, total_tokens=21),
    )
    sdk = SimpleNamespace(responses=SimpleNamespace(create=lambda **_kwargs: response))
    monkeypatch.setattr(chat_module, "OpenAI", lambda **_kwargs: sdk)
    settings = Settings(
        _env_file=None, llm_provider="openai", openai_api_key="test-key"
    )
    client = TracedChatClient(OpenAIChatClient(settings))

    with caplog.at_level(logging.INFO, logger="yoyo.model"):
        with trace_run("run-123"):
            result = client.complete(
                "私人系统提示", (ChatInput("user", "私人问题"),), 100
            )

    assert result == "可以回答"
    usage = next(
        record
        for record in caplog.records
        if record.msg.startswith("model.complete.usage")
    )
    assert usage.run_id == "run-123"
    assert "run_id=run-123" in usage.getMessage()
    assert usage.input_tokens == 17
    assert usage.output_tokens == 4
    assert usage.total_tokens == 21
    assert "私人系统提示" not in caplog.text
    assert "私人问题" not in caplog.text
    assert current_run_id() is None
