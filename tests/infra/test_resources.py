"""基础设施资源在装配失败和关闭时都必须释放。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.infra.resources as infra_resources
import server.main as server_main
from server.config import Settings
from server.infra.database import Database


def test_redis_uses_configured_connection_and_read_timeouts(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        upload_dir=tmp_path,
        redis_socket_timeout_seconds=3.5,
    )
    resources = infra_resources.InfraResources.create(settings)
    try:
        options = resources.redis.connection_pool.connection_kwargs
        assert options["socket_timeout"] == 3.5
        assert options["socket_connect_timeout"] == 3.5
    finally:
        resources.close()


def test_resource_assembly_releases_connections_after_late_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[str] = []
    original_database_close = Database.close
    original_redis_close = infra_resources.Redis.close

    def close_database(resource: Database) -> None:
        closed.append("database")
        original_database_close(resource)

    def close_redis(resource: infra_resources.Redis) -> None:
        closed.append("redis")
        original_redis_close(resource)

    def fail_chat(_settings: Settings) -> None:
        raise RuntimeError("model setup failed")

    monkeypatch.setattr(Database, "close", close_database)
    monkeypatch.setattr(infra_resources.Redis, "close", close_redis)
    monkeypatch.setattr(infra_resources, "create_chat_client", fail_chat)
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        upload_dir=tmp_path,
    )

    with pytest.raises(RuntimeError, match="model setup failed"):
        infra_resources.InfraResources.create(settings)

    # Redis 对象析构时也会调用 close；这里验证装配失败当场完成的逆序清理。
    assert closed[:2] == ["redis", "database"]
    assert closed.count("database") == 1


def test_app_startup_releases_infra_when_module_assembly_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[bool] = []

    class StubResources:
        database = object()

        def close(self) -> None:
            closed.append(True)

    def fail_users(*_args: object) -> None:
        raise RuntimeError("users setup failed")

    monkeypatch.setattr(
        server_main.InfraResources, "create", lambda _settings: StubResources()
    )
    monkeypatch.setattr(server_main.UsersModule, "create", fail_users)
    monkeypatch.setattr(
        server_main, "create_reset_delivery", lambda _settings: object()
    )
    application = server_main.create_app(Settings(_env_file=None))

    with pytest.raises(RuntimeError, match="users setup failed"):
        with TestClient(application):
            pass

    assert closed == [True]


def test_infra_close_releases_database_even_if_redis_close_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        upload_dir=tmp_path,
    )
    resources = infra_resources.InfraResources.create(settings)
    database_closed: list[bool] = []
    original_database_close = resources.database.close

    def close_database() -> None:
        database_closed.append(True)
        original_database_close()

    def fail_redis_close() -> None:
        raise RuntimeError("redis close failed")

    monkeypatch.setattr(resources.database, "close", close_database)
    monkeypatch.setattr(resources.redis, "close", fail_redis_close)

    with pytest.raises(RuntimeError, match="redis close failed"):
        resources.close()

    assert database_closed == [True]
