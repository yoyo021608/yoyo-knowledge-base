"""验证提问入口只协调公开模块能力，并能幂等保存最终回答。"""

from pathlib import Path

from fastapi.testclient import TestClient

from server.agent.module import AgentModule
from server.agent.types import ContextInput, RetrievalPlan, SearchHitContext
from server.config import Settings
from server.controller.agent import get_agent
from server.controller.sessions import get_sessions
from server.controller.users import get_users
from server.controller.users.reset_delivery import DevelopmentHttpResetDelivery
from server.infra.chat import FakeChatClient
from server.infra.database import Base, Database
from server.main import create_app
from server.sessions import SessionsModule
from server.users.module import UsersModule


class ApiDocumentsPort:
    def search(self, user_id: str, plan: RetrievalPlan) -> tuple[SearchHitContext, ...]:
        del user_id, plan
        return (
            SearchHitContext(
                "document-1",
                "version-1",
                "Python 资料",
                "Python 是一种编程语言。",
                "chunk-1",
                None,
                0.9,
            ),
        )

    def validate_sources(
        self,
        user_id: str,
        hits: tuple[SearchHitContext, ...],
        *,
        allow_historical_versions: bool = False,
    ) -> tuple[SearchHitContext, ...]:
        del user_id, allow_historical_versions
        return hits


def test_question_flow_saves_answer_and_reuses_request_id(tmp_path: Path) -> None:
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-that-is-not-used-in-production",
        upload_dir=tmp_path / "uploads",
    )
    users = UsersModule.create(database, settings, DevelopmentHttpResetDelivery())
    sessions = SessionsModule.create(database)
    agent = AgentModule.create(database, settings, FakeChatClient(), ApiDocumentsPort())
    profile = users.registration.register("alice@example.com", "correct-horse-1")
    login = users.login_sessions.login("alice@example.com", "correct-horse-1")
    session = sessions.management.create(profile.id, "知识问答")

    application = create_app(settings)
    application.dependency_overrides[get_users] = lambda: users
    application.dependency_overrides[get_sessions] = lambda: sessions
    application.dependency_overrides[get_agent] = lambda: agent
    client = TestClient(application)
    headers = {"Authorization": f"Bearer {login.token.access_token}"}
    body = {
        "session_id": session.id,
        "request_id": "request-http-1",
        "question": "Python 是什么",
        "mode": "quick",
    }

    first = client.post("/api/agent/questions", headers=headers, json=body)
    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    completed = client.get(f"/api/agent/runs/{first.json()['id']}", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    repeated = client.post("/api/agent/questions", headers=headers, json=body)
    assert repeated.status_code == 202
    assert repeated.json()["id"] == first.json()["id"]
    messages = sessions.history.list(session.id, profile.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[-1].citations[0].quote == "Python 是一种编程语言。"

    # 取消接口必须同时清理 sessions 中的活动 Run，避免会话永久忙碌。
    cancelled_session = sessions.management.create(profile.id, "取消测试")
    queued = agent.runs.create_run(
        cancelled_session.id,
        profile.id,
        "request-http-cancel",
        "quick",
        ContextInput("待取消问题", (), (), agent.default_budget),
    )
    sessions.management.try_claim_run(cancelled_session.id, profile.id, queued.run.id)
    cancelled = client.post(f"/api/agent/runs/{queued.run.id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert (
        sessions.management.get(cancelled_session.id, profile.id).active_run_id is None
    )
    database.close()
