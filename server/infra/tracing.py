"""在一次运行的调用链中传递技术追踪标识，不保存业务状态。"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_RUN_ID: ContextVar[str | None] = ContextVar("model_trace_run_id", default=None)


def current_run_id() -> str | None:
    return _RUN_ID.get()


@contextmanager
def trace_run(run_id: str) -> Iterator[None]:
    """让同一 Run 的模型和 Embedding 调用共享标识，并在结束后恢复原值。"""
    token = _RUN_ID.set(run_id)
    try:
        yield
    finally:
        _RUN_ID.reset(token)
