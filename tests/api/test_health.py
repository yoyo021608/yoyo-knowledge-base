from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    """健康检查接口可用，说明应用装配和路由挂载正常。"""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
