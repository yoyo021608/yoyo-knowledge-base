"""从公开 HTTP 接口验证 MVP 的跨模块知识问答业务链。"""

from pathlib import Path

from fastapi.testclient import TestClient

from server.agent.module import AgentModule
from server.config import Settings
from server.controller.agent import get_agent
from server.controller.agent.document_port import DocumentsSearchBridge
from server.controller.documents import get_documents
from server.controller.sessions import get_sessions
from server.controller.users import get_users
from server.controller.users.reset_delivery import DevelopmentHttpResetDelivery
from server.documents import DocumentsModule
from server.infra.chat import FakeChatClient
from server.infra.database import Base, Database
from server.infra.files import LocalFileStorage
from server.main import create_app
from server.sessions import SessionsModule
from server.users.module import UsersModule


def test_mvp_business_flow_survives_refresh_and_replays_versioned_citations(
    tmp_path: Path,
) -> None:
    """注册、入库、问答和刷新回放必须通过同一套公开边界完成。"""

    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-that-is-not-used-in-production",
        upload_dir=tmp_path / "uploads",
    )
    users = UsersModule.create(database, settings, DevelopmentHttpResetDelivery())
    documents = DocumentsModule.create(
        database,
        LocalFileStorage(tmp_path / "uploads"),
    )
    sessions = SessionsModule.create(database)
    agent = AgentModule.create(
        database,
        settings,
        FakeChatClient(),
        DocumentsSearchBridge(documents),
    )

    application = create_app(settings)
    application.dependency_overrides[get_users] = lambda: users
    application.dependency_overrides[get_documents] = lambda: documents
    application.dependency_overrides[get_sessions] = lambda: sessions
    application.dependency_overrides[get_agent] = lambda: agent
    client = TestClient(application)
    refreshed_client: TestClient | None = None

    try:
        registered = client.post(
            "/api/users/register",
            json={"email": "alice@example.com", "password": "correct-horse-1"},
        )
        assert registered.status_code == 201

        logged_in = client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "correct-horse-1"},
        )
        assert logged_in.status_code == 200
        token = logged_in.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/users/me", headers=headers).status_code == 200

        imported = client.post(
            "/api/documents/import",
            headers=headers,
            json={
                "title": "可恢复知识问答",
                "content": (
                    "可恢复运行会持久化步骤快照和事件序号。"
                    "回答引用绑定具体文档版本与原文片段，"
                    "文档更新后仍能解释历史回答的依据。"
                ),
                "source_type": "markdown",
                "source_title": "可恢复知识问答笔记",
                "tags": ["架构", "可恢复运行"],
            },
        )
        assert imported.status_code == 201
        imported_body = imported.json()
        assert imported_body["index_status"] == "ready"

        index = client.get(
            f"/api/documents/{imported_body['document_id']}/index",
            headers=headers,
        )
        assert index.status_code == 200
        assert index.json()["status"] == "ready"

        search = client.post(
            "/api/documents/search",
            headers=headers,
            json={
                "text": "可恢复运行如何保留历史回答依据",
                "mode": "hybrid",
                "limit": 8,
            },
        )
        assert search.status_code == 200
        assert search.json()[0]["version_id"] == imported_body["version_id"]

        created_session = client.post(
            "/api/sessions",
            headers=headers,
            json={"name": "可恢复运行研究"},
        )
        assert created_session.status_code == 201
        session_id = created_session.json()["id"]

        question = {
            "session_id": session_id,
            "request_id": "mvp-flow-request-1",
            "question": "可恢复运行如何保留历史回答的依据",
            "mode": "quick",
        }
        accepted = client.post("/api/agent/questions", headers=headers, json=question)
        assert accepted.status_code == 202
        run_id = accepted.json()["id"]

        completed = client.get(f"/api/agent/runs/{run_id}", headers=headers)
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

        events = client.get(
            f"/api/agent/runs/{run_id}/events",
            headers=headers,
            params={"after_seq": 0, "limit": 100},
        )
        assert events.status_code == 200
        event_values = events.json()
        assert [event["event_seq"] for event in event_values] == list(
            range(1, len(event_values) + 1)
        )
        assert event_values[-1]["event_type"] == "run.completed"

        messages = client.get(f"/api/sessions/{session_id}/messages", headers=headers)
        assert messages.status_code == 200
        message_values = messages.json()
        assert [message["role"] for message in message_values] == [
            "user",
            "assistant",
        ]
        answer = message_values[-1]
        assert "可恢复运行" in answer["content"]
        assert len(answer["citations"]) == 1
        citation = answer["citations"][0]
        assert citation["document_id"] == imported_body["document_id"]
        assert citation["document_version_id"] == imported_body["version_id"]
        assert "步骤快照" in citation["quote"]

        replayed_citations = client.get(
            f"/api/sessions/{session_id}/messages/{answer['id']}/citations",
            headers=headers,
        )
        assert replayed_citations.status_code == 200
        assert replayed_citations.json() == answer["citations"]

        # 模拟页面刷新后的新客户端：只复用令牌，通过持久化数据恢复会话。
        refreshed_client = TestClient(application)
        refreshed_messages = refreshed_client.get(
            f"/api/sessions/{session_id}/messages", headers=headers
        )
        assert refreshed_messages.status_code == 200
        assert refreshed_messages.json() == message_values

        # 网络重试使用相同 request_id 时复用同一个 Run，不重复保存消息。
        repeated = refreshed_client.post(
            "/api/agent/questions", headers=headers, json=question
        )
        assert repeated.status_code == 202
        assert repeated.json()["id"] == run_id
        repeated_messages = refreshed_client.get(
            f"/api/sessions/{session_id}/messages", headers=headers
        )
        assert len(repeated_messages.json()) == 2

        session_after_run = refreshed_client.get(
            f"/api/sessions/{session_id}", headers=headers
        )
        assert session_after_run.status_code == 200
        assert session_after_run.json()["active_run_id"] is None
    finally:
        if refreshed_client is not None:
            refreshed_client.close()
        client.close()
        application.dependency_overrides.clear()
        database.close()
