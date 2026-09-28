import pytest
from pydantic import ValidationError

from server.config import Settings


def test_openai_provider_requires_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai", openai_api_key="")


def test_fake_provider_does_not_require_api_key() -> None:
    settings = Settings(_env_file=None, llm_provider="fake", openai_api_key="")
    assert settings.llm_provider == "fake"


def test_database_url_rejects_unsupported_driver() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://localhost/example")


def test_openai_base_url_requires_http_protocol() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, openai_base_url="api.example.com/v1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, openai_base_url="https://")


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production")
