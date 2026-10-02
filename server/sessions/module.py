"""sessions 内部装配；外部只能取得这里公开的领域能力。"""

from dataclasses import dataclass

from server.infra.database import Database
from server.sessions.history import MessageHistory
from server.sessions.management import SessionManagement
from server.sessions.results import InteractionResults


@dataclass(frozen=True, slots=True)
class SessionsModule:
    management: SessionManagement
    history: MessageHistory
    results: InteractionResults

    @classmethod
    def create(cls, database: Database) -> "SessionsModule":
        """三个能力共享事务入口，但不互相承担业务职责。"""
        return cls(
            management=SessionManagement(database),
            history=MessageHistory(database),
            results=InteractionResults(database),
        )
