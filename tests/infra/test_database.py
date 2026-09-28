from pathlib import Path

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from server.infra.database import Database


class DatabaseBase(DeclarativeBase):
    pass


class Record(DatabaseBase):
    __tablename__ = "test_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(50))


@pytest.fixture
def database() -> Database:
    resource = Database("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(resource.engine)
    try:
        yield resource
    finally:
        resource.close()


def test_transaction_commits_on_success(database: Database) -> None:
    with database.transaction() as session:
        session.add(Record(value="committed"))

    with database.session() as session:
        values = session.scalars(select(Record.value)).all()

    assert values == ["committed"]


def test_transaction_rolls_back_on_failure(database: Database) -> None:
    with pytest.raises(RuntimeError):
        with database.transaction() as session:
            session.add(Record(value="rolled-back"))
            raise RuntimeError("force rollback")

    with database.session() as session:
        values = session.scalars(select(Record.value)).all()

    assert values == []


def test_check_connection_executes_probe(database: Database) -> None:
    database.check_connection()


def test_file_backed_sqlite_uses_supported_connection_options(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'database.db'}")
    try:
        database.check_connection()
    finally:
        database.close()
