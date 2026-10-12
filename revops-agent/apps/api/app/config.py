from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me-dev-only-change-me-dev-only-change-me"
DEV_INTERNAL_KEY = "dev-internal-key"
LOCAL_ENVS = ("local", "test")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    database_url: str = "postgresql+asyncpg://app:app@localhost:5433/revops"
    database_admin_url: str = "postgresql+asyncpg://admin:admin@localhost:5433/revops"
    database_migrator_url: str = "postgresql+psycopg://owner:owner@localhost:5433/revops"
    redis_url: str = "redis://localhost:6379/0"

    api_jwt_secret: str = DEV_JWT_SECRET
    api_jwt_audience: str = "revops-api"
    token_enc_keys: str = ""

    public_api_url: str = "http://localhost:8000"
    web_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_email: str = "notifications@revops.internal"
    resend_api_key: str = ""
    email_provider: Literal["smtp", "resend", "console"] = "smtp"

    mock_api: bool = False
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120  # default per user (per IP when unauthenticated)
    rate_limit_sensitive_per_minute: int = 30  # auth-sensitive and ingest routes
    mock_auth: bool = True  # enforce JWT + role checks in mock mode too
    real_routers: str = ""
    internal_api_key: str = DEV_INTERNAL_KEY
    ai_mode: Literal["template", "external"] = "template"
    ai_service_url: str = ""  # apps/ai base URL (AI_MODE=external); empty = AI upgrades are off
    ai_service_timeout_s: float = 10.0
    ai_extract_wait_s: float = 90.0  # max wait for signal extraction before a manual run
    feature_email_send: bool = False

    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""

    @model_validator(mode="after")
    def _refuse_unsafe_defaults_outside_local(self) -> "Settings":
        """Staging/prod must never run with the dev secrets that ship in this file."""
        if self.app_env in LOCAL_ENVS:
            return self
        problems: list[str] = []
        if self.api_jwt_secret == DEV_JWT_SECRET or len(self.api_jwt_secret) < 32:
            problems.append(
                "API_JWT_SECRET must be set to a unique value of at least 32 characters"
            )
        if self.internal_api_key == DEV_INTERNAL_KEY or len(self.internal_api_key) < 16:
            problems.append(
                "INTERNAL_API_KEY must be set to a unique value of at least 16 characters"
            )
        if not self.token_enc_keys:
            problems.append("TOKEN_ENC_KEYS must be set (id:base64-32-bytes)")
        if self.mock_api and not self.mock_auth:
            problems.append("MOCK_AUTH=false is only allowed in APP_ENV=local")
        if problems:
            raise ValueError(
                f"Unsafe configuration for APP_ENV={self.app_env}: " + "; ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
