from pathlib import Path

from fastapi.testclient import TestClient

from server.config import Settings
from server.controller.sessions import get_sessions
from server.controller.users import get_users
from server.controller.users.reset_delivery import DevelopmentHttpResetDelivery
from server.infra.database import Base, Database
from server.main import create_app
from server.sessions import SessionsModule
from server.sessions.types import CitationInput
from server.users.module import UsersModule


def test_sessions_http_flow_keeps_identity_and_module_boundaries(
    tmp_path: Path,
) -> None:
    """HTTP 层只传可信身份，并通过 sessions 的公开能力保存和回放。"""
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
    users.registration.register("alice@example.com", "correct-horse-1")
    users.registration.register("bob@example.com", "correct-horse-2")
    alice = users.login_sessions.login("alice@example.com", "correct-horse-1")
    bob = users.login_sessions.login("bob@example.com", "correct-horse-2")
    app = create_app(settings)
    app.dependency_overrides[get_users] = lambda: users
    app.dependency_overrides[get_sessions] = lambda: sessions
    client = TestClient(app)
    alice_headers = {"Authorization": f"Bearer {alice.token.access_token}"}
    bob_headers = {"Authorization": f"Bearer {bob.token.access_token}"}

    created = client.post(
        "/api/sessions",
        headers=alice_headers,
        json={"name": "版本研究", "user_id": bob.profile.id},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert created.json()["user_id"] == alice.profile.id
    assert (
        client.get(f"/api/sessions/{session_id}", headers=bob_headers).status_code
        == 404
    )

    # Run 领取属于 controller 与 Agent 的内部协调，不暴露给浏览器客户端。
    sessions.management.try_claim_run(session_id, alice.profile.id, "run-1")
    assert (
        client.post(
            f"/api/sessions/{session_id}/runs/claim",
            headers=alice_headers,
            json={"run_id": "run-1"},
        ).status_code
        == 404
    )
    answer = sessions.history.save_answer(
        session_id,
        alice.profile.id,
        "run-1",
        "结论",
        (
            CitationInput(
                document_id="doc",
                document_version_id="v1",
                chunk_id="c1",
                title_snapshot="资料",
                quote="原始证据",
            ),
        ),
    )
    assert answer.content == "结论"
    assert (
        client.post(
            f"/api/sessions/{session_id}/messages/assistant",
            headers=alice_headers,
            json={"run_id": "run-1", "content": "伪造回答"},
        ).status_code
        == 404
    )
    replay = client.get(f"/api/sessions/{session_id}/messages", headers=alice_headers)
    assert replay.json()[0]["citations"][0]["quote"] == "原始证据"
    database.close()
