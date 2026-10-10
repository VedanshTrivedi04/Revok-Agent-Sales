from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    database_url: str = "postgresql+asyncpg://app:app@localhost:5433/revops"
    database_admin_url: str = "postgresql+asyncpg://admin:admin@localhost:5433/revops"
    database_migrator_url: str = "postgresql+psycopg://owner:owner@localhost:5433/revops"
    redis_url: str = "redis://localhost:6379/0"

    api_jwt_secret: str = "dev-only-change-me-dev-only-change-me-dev-only-change-me"
    api_jwt_audience: str = "revops-api"
    token_enc_keys: str = ""

    public_api_url: str = "http://localhost:8000"
    web_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    smtp_host: str = "localhost"
    smtp_port: int = 1025

    mock_api: bool = False
    real_routers: str = ""
    ai_mode: Literal["template", "external"] = "template"
    feature_email_send: bool = False

    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
