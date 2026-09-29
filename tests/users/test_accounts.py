from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from server.config import Settings
from server.controller.reset_delivery import (
    DevelopmentHttpResetDelivery,
    ProductionResetDelivery,
)
from server.controller.users import get_users
from server.infra.database import Base, Database
from server.main import create_app
from server.users.errors import (
    EmailAlreadyRegistered,
    InvalidAccessToken,
    InvalidCredentials,
    InvalidResetToken,
)
from server.users.models import PasswordResetToken
from server.users.module import UsersModule


@pytest.fixture
def accounts() -> Iterator[tuple[UsersModule, Database]]:
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-that-is-not-used-in-production",
        password_reset_token_ttl_minutes=5,
    )
    users = UsersModule.create(database, settings, DevelopmentHttpResetDelivery())
    try:
        yield users, database
    finally:
        database.close()


def test_registration_normalizes_email_and_rejects_duplicate(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    profile = users.registration.register("  Alice@Example.COM ", "correct-horse-1")

    assert profile.email == "alice@example.com"
    with pytest.raises(EmailAlreadyRegistered):
        users.registration.register("alice@example.com", "different-password")


def test_registration_internal_lookup_returns_credentials_only_inside_module(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    created = users.registration.register("Alice@Example.COM", "correct-horse-1")

    stored = users.registration.find_by_email(" alice@example.com ")

    assert stored is not None
    assert stored.id == created.id
    assert stored.email == "alice@example.com"
    assert stored.password_hash != "correct-horse-1"


def test_login_identity_and_logout_revoke_only_current_session(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    profile = users.registration.register("alice@example.com", "correct-horse-1")
    first = users.login_sessions.login("alice@example.com", "correct-horse-1")
    second = users.login_sessions.login("alice@example.com", "correct-horse-1")

    identity = users.identity.require(first.token.access_token)
    assert identity.user_id == profile.id
    assert identity.email == profile.email

    users.login_sessions.logout(first.token.access_token)
    with pytest.raises(InvalidAccessToken):
        users.identity.require(first.token.access_token)
    assert users.identity.require(second.token.access_token).user_id == profile.id


def test_login_returns_same_public_error_for_unknown_email_or_bad_password(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    users.registration.register("alice@example.com", "correct-horse-1")

    with pytest.raises(InvalidCredentials, match="邮箱或密码错误"):
        users.login_sessions.login("missing@example.com", "wrong-password")
    with pytest.raises(InvalidCredentials, match="邮箱或密码错误"):
        users.login_sessions.login("alice@example.com", "wrong-password")


def test_change_password_revokes_every_login_session(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    profile = users.registration.register("alice@example.com", "correct-horse-1")
    first = users.login_sessions.login("alice@example.com", "correct-horse-1")
    second = users.login_sessions.login("alice@example.com", "correct-horse-1")

    users.passwords.change_password(
        profile.id,
        "correct-horse-1",
        "new-correct-horse-2",
    )

    with pytest.raises(InvalidAccessToken):
        users.identity.require(first.token.access_token)
    with pytest.raises(InvalidAccessToken):
        users.identity.require(second.token.access_token)
    with pytest.raises(InvalidCredentials):
        users.login_sessions.login("alice@example.com", "correct-horse-1")
    users.login_sessions.login("alice@example.com", "new-correct-horse-2")


def test_password_reset_is_hashed_one_time_and_revokes_sessions(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, database = accounts
    users.registration.register("alice@example.com", "correct-horse-1")
    login = users.login_sessions.login("alice@example.com", "correct-horse-1")

    reset_token = users.passwords.request_reset("alice@example.com")
    assert reset_token is not None
    with database.session() as session:
        stored = session.scalar(select(PasswordResetToken))
        assert stored is not None
        assert stored.token_hash != reset_token

    users.passwords.reset_password(reset_token, "reset-correct-horse-3")

    with pytest.raises(InvalidResetToken):
        users.passwords.reset_password(reset_token, "another-password-4")
    with pytest.raises(InvalidAccessToken):
        users.identity.require(login.token.access_token)
    users.login_sessions.login("alice@example.com", "reset-correct-horse-3")


def test_password_reset_request_hides_unknown_accounts(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    missing = users.passwords.request_reset("missing@example.com")
    invalid = users.passwords.request_reset("not-an-email")
    assert missing
    assert invalid


def test_users_http_flow(accounts: tuple[UsersModule, Database]) -> None:
    users, _ = accounts
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-that-is-not-used-in-production",
    )
    application = create_app(settings)
    application.dependency_overrides[get_users] = lambda: users
    client = TestClient(application)

    register = client.post(
        "/api/users/register",
        json={"email": "alice@example.com", "password": "correct-horse-1"},
    )
    assert register.status_code == 201
    assert "password" not in register.json()

    login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    current = client.get("/api/users/me", headers=headers)
    assert current.status_code == 200
    assert current.json()["email"] == "alice@example.com"

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 204
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_reset_http_response_does_not_reveal_account_existence(
    accounts: tuple[UsersModule, Database],
) -> None:
    users, _ = accounts
    users.registration.register("alice@example.com", "correct-horse-1")
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-that-is-not-used-in-production",
    )
    application = create_app(settings)
    application.dependency_overrides[get_users] = lambda: users
    client = TestClient(application)

    known = client.post(
        "/api/auth/password-reset/request",
        json={"email": "alice@example.com"},
    )
    unknown = client.post(
        "/api/auth/password-reset/request",
        json={"email": "missing@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json()["message"] == unknown.json()["message"]
    assert known.json()["development_reset_token"]
    assert unknown.json()["development_reset_token"]

    confirm = client.post(
        "/api/auth/password-reset/confirm",
        json={
            "token": known.json()["development_reset_token"],
            "new_password": "reset-through-http-2",
        },
    )
    assert confirm.status_code == 204


def test_production_reset_response_never_exposes_raw_token(
    accounts: tuple[UsersModule, Database],
) -> None:
    _, database = accounts
    settings = Settings(
        app_env="production",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="production-test-secret-with-more-than-32-characters",
    )
    users = UsersModule.create(database, settings, ProductionResetDelivery())
    users.registration.register("alice@example.com", "correct-horse-1")
    application = create_app(settings)
    application.dependency_overrides[get_users] = lambda: users
    client = TestClient(application)

    response = client.post(
        "/api/auth/password-reset/request",
        json={"email": "alice@example.com"},
    )
    unknown = client.post(
        "/api/auth/password-reset/request",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == unknown.status_code == 503
    assert response.json() == unknown.json() == {"detail": "密码重置通知服务尚未配置"}
