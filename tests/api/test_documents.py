from pathlib import Path

from fastapi.testclient import TestClient

from server.config import Settings
from server.controller.documents import get_documents
from server.controller.users import get_users
from server.controller.users.reset_delivery import DevelopmentHttpResetDelivery
from server.documents import DocumentsModule
from server.infra.database import Base, Database
from server.infra.files import LocalFileStorage
from server.main import create_app
from server.users.module import UsersModule


def test_documents_http_flow_uses_authenticated_identity(tmp_path: Path) -> None:
    """HTTP 正文不能覆盖身份，录入、检索、版本和归档通过公开端口完成。"""
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-that-is-not-used-in-production",
        upload_dir=tmp_path / "uploads",
    )
    users = UsersModule.create(database, settings, DevelopmentHttpResetDelivery())
    documents = DocumentsModule.create(database, LocalFileStorage(tmp_path / "uploads"))
    users.registration.register("alice@example.com", "correct-horse-1")
    users.registration.register("bob@example.com", "correct-horse-2")
    alice = users.login_sessions.login("alice@example.com", "correct-horse-1")
    bob = users.login_sessions.login("bob@example.com", "correct-horse-2")

    application = create_app(settings)
    application.dependency_overrides[get_users] = lambda: users
    application.dependency_overrides[get_documents] = lambda: documents
    client = TestClient(application)
    alice_headers = {"Authorization": f"Bearer {alice.token.access_token}"}
    bob_headers = {"Authorization": f"Bearer {bob.token.access_token}"}

    imported = client.post(
        "/api/documents/import",
        headers=alice_headers,
        json={
            "title": "接口边界",
            "content": "- [[controller]] 只装配 `DocumentsModule` 公开业务能力。",
            "source_type": "note",
            "tags": ["架构"],
            # 即使请求额外传 user_id，Pydantic 也不会把它交给领域输入。
            "user_id": bob.profile.id,
        },
    )
    assert imported.status_code == 201
    document_id = imported.json()["document_id"]
    assert (
        client.get(f"/api/documents/{document_id}", headers=bob_headers).status_code
        == 404
    )

    search = client.post(
        "/api/documents/search",
        headers=alice_headers,
        json={"text": "公开业务能力", "mode": "hybrid", "limit": 8},
    )
    assert search.status_code == 200
    assert search.json()[0]["document_id"] == document_id

    knowledge = client.get(
        f"/api/documents/{document_id}/knowledge", headers=alice_headers
    )
    assert knowledge.status_code == 200
    assert {entity["name"] for entity in knowledge.json()["entities"]} >= {
        "controller",
        "DocumentsModule",
    }
    assert (
        client.get(
            f"/api/documents/{document_id}/knowledge", headers=bob_headers
        ).status_code
        == 404
    )

    updated = client.put(
        f"/api/documents/{document_id}",
        headers=alice_headers,
        json={
            "title": "接口边界 v2",
            "content": "更新必须创建新版本。",
            "tags": ["架构"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    versions = client.get(
        f"/api/documents/{document_id}/versions", headers=alice_headers
    )
    assert [item["version"] for item in versions.json()] == [2, 1]

    assert (
        client.post(
            f"/api/documents/{document_id}/archive", headers=alice_headers
        ).status_code
        == 204
    )
    assert client.get("/api/documents", headers=alice_headers).json() == []
    database.close()
