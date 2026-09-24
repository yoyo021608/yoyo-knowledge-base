from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend assembly."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    llm_provider: str = "fake"
    database_url: str = (
        "postgresql+psycopg://postgres:change-me@localhost:5432/knowledge_base"
    )
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-this-local-secret"
    password_reset_token_ttl_minutes: int = 15
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4.1-mini"
    upload_dir: str = "./data/uploads"
    cors_origins: str = "http://localhost:5173"

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
