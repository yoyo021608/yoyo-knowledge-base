from collections.abc import Iterator

import pytest

from server.infra.database import Base, Database
from server.sessions import SessionsModule
from server.sessions import models as session_models  # noqa: F401
from server.users.models import User


@pytest.fixture
def sessions_context() -> Iterator[tuple[Database, SessionsModule]]:
    """为会话测试创建包含用户归属关系的隔离数据库。"""
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    with database.transaction() as db:
        db.add_all(
            [
                User(id="user-a", email="a@example.com", password_hash="unused"),
                User(id="user-b", email="b@example.com", password_hash="unused"),
            ]
        )
    try:
        yield database, SessionsModule.create(database)
    finally:
        database.close()
