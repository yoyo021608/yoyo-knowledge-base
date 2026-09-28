from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Shared SQLAlchemy metadata base; domain models remain in their modules."""


class Database:
    """Owns the database engine and transaction lifecycle."""

    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout_seconds: int = 30,
        connect_timeout_seconds: int = 10,
    ) -> None:
        if url.startswith("sqlite+pysqlite://"):
            if url.startswith("sqlite+pysqlite:///:memory:"):
                self.engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                self.engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    connect_args={"check_same_thread": False},
                )
        else:
            self.engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout_seconds,
                connect_args={"connect_timeout": connect_timeout_seconds},
            )
        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a session without implicitly committing a transaction."""

        with self._session_factory() as session:
            yield session

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Commit on success and roll back every failure."""

        with self._session_factory() as session, session.begin():
            yield session

    def check_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def close(self) -> None:
        self.engine.dispose()
