from pathlib import Path
from uuid import uuid4

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Keep each test run isolated from locked Windows temp directories."""

    if config.option.basetemp is None:
        config.option.basetemp = Path(f".pytest-run-{uuid4().hex}")
