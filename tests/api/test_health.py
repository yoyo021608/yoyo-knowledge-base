from fastapi.testclient import TestClient

from server.infra.resources import InfraResources
from server.main import app, create_app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_exposes_infrastructure_resources() -> None:
    application = create_app()

    with TestClient(application):
        assert isinstance(application.state.infra, InfraResources)
