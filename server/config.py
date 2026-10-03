from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend assembly."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    llm_provider: Literal["fake", "openai"] = "fake"
    database_url: str = (
        "postgresql+psycopg://postgres:change-me@localhost:5432/knowledge_base"
    )
    database_pool_size: int = Field(default=5, gt=0)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout_seconds: int = Field(default=30, gt=0)
    database_connect_timeout_seconds: int = Field(default=10, gt=0)
    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout_seconds: float = Field(default=5.0, gt=0)
    redis_job_queue_name: str = Field(default="knowledge-base:jobs", min_length=1)
    jwt_secret: str = "change-this-local-secret"
    password_reset_token_ttl_minutes: int = Field(default=15, gt=0)
    openai_api_key: str = ""
    openai_base_url: str = Field(default="https://api.openai.com/v1", min_length=1)
    embedding_model: str = Field(default="text-embedding-3-small", min_length=1)
    chat_model: str = Field(default="gpt-4.1-mini", min_length=1)
    openai_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    openai_max_retries: int = Field(default=2, ge=0, le=5)
    agent_model_window: int = Field(default=16_000, gt=0)
    agent_reserved_output_tokens: int = Field(default=2_000, gt=0)
    agent_safety_margin: int = Field(default=500, ge=0)
    agent_history_budget: int = Field(default=3_000, ge=0)
    agent_evidence_budget: int = Field(default=8_000, ge=0)
    agent_retrieval_limit: int = Field(default=8, ge=1, le=50)
    agent_max_retrieval_retries: int = Field(default=1, ge=0, le=3)
    agent_retrieval_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    agent_recovery_interval_seconds: float = Field(default=10.0, gt=0, le=300)
    upload_dir: Path = Path("./data/uploads")
    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        supported_schemes = ("postgresql+psycopg://", "sqlite+pysqlite://")
        if not value.startswith(supported_schemes):
            raise ValueError("DATABASE_URL must use psycopg or sqlite+pysqlite")
        parsed = urlsplit(value)
        if value.startswith("postgresql+psycopg://") and parsed.hostname is None:
            raise ValueError("DATABASE_URL must include a PostgreSQL host")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        if urlsplit(value).hostname is None:
            raise ValueError("REDIS_URL must include a host")
        return value

    @field_validator("openai_base_url")
    @classmethod
    def validate_openai_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("OPENAI_BASE_URL must use http:// or https://")
        if urlsplit(value).hostname is None:
            raise ValueError("OPENAI_BASE_URL must include a host")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_environment_secrets(self) -> "Settings":
        if self.llm_provider == "openai" and not self.openai_api_key.strip():
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if self.app_env == "production" and (
            self.jwt_secret == "change-this-local-secret" or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "JWT_SECRET must be changed and contain at least 32 characters"
            )
        usable = (
            self.agent_model_window
            - self.agent_reserved_output_tokens
            - self.agent_safety_margin
        )
        if usable <= 0:
            raise ValueError("Agent model window must leave room for input")
        if self.agent_history_budget + self.agent_evidence_budget > usable:
            raise ValueError(
                "Agent history and evidence budgets exceed the input window"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins: list[str] = []
        for origin in self.cors_origins.split(","):
            stripped = origin.strip()
            if stripped:
                origins.append(stripped)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
