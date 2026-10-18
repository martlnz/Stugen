from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    domain: str = "localhost"
    app_url: str = "http://localhost"

    database_url: str = "postgresql+asyncpg://stugen:stugen@postgres:5432/stugen"
    database_url_sync: str = "postgresql+psycopg://stugen:stugen@postgres:5432/stugen"
    redis_url: str = "redis://redis:6379/0"

    s3_endpoint: str = "http://minio:9000"
    s3_bucket: str = "stugen"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost/api/auth/google/callback"
    session_secret: str = "dev-only-secret"
    session_days: int = 7
    session_renew_days: int = 3

    llm_provider: Literal["openai_compatible", "openai", "anthropic", "fake"] = "openai_compatible"
    llm_model: str = "deepseek-v4-pro"
    llm_model_fast: str = "deepseek-flash"
    llm_api_key: str = ""
    llm_base_url: str | None = "https://api.deepseek.com"
    llm_max_concurrency: int = 4
    llm_timeout_s: float = 120.0
    llm_max_tokens: int = 8000
    content_language: Literal["vi", "source"] = "vi"

    max_upload_mb: int = 20
    max_pages: int = 200
    celery_concurrency: int = 2

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
