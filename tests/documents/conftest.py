from collections.abc import Iterator
from pathlib import Path

import pytest

from server.documents import DocumentsModule
from server.documents import models as document_models  # noqa: F401
from server.infra.database import Base, Database
from server.infra.files import LocalFileStorage
from server.users.models import User


@pytest.fixture
def document_context(tmp_path: Path) -> Iterator[tuple[Database, DocumentsModule]]:
    """为每个文档测试创建隔离数据库和文件目录。"""
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    with database.transaction() as session:
        session.add_all(
            [
                User(id="user-a", email="a@example.com", password_hash="unused"),
                User(id="user-b", email="b@example.com", password_hash="unused"),
            ]
        )
    module = DocumentsModule.create(database, LocalFileStorage(tmp_path / "uploads"))
    try:
        yield database, module
    finally:
        database.close()
