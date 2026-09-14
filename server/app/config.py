from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：只从环境变量和 .env 读取，不在代码里写死。"""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    llm_provider: str = "fake"

    database_url: str = ""
    redis_url: str = ""

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
        """把逗号分隔的 CORS 来源拆成列表，供中间件直接使用。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """进程内复用同一份配置，避免每次请求重复解析环境变量。"""
    return Settings()
