from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repository root, so alembic works from backend/
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kinwise"
    jwt_secret: str = "dev-only-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    environment: str = "development"
    auth_rate_limit_enabled: bool = True
    auto_create_schema: bool = False
    daily_message_limit: int = 200

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_seconds: float = 12.0

    backboard_api_key: str = ""
    backboard_base_url: str = "https://app.backboard.io/api"

    spectrum_bridge_url: str = ""
    spectrum_bridge_token: str = ""

    cors_origins: list[str] = Field(default_factory=list)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def backboard_configured(self) -> bool:
        return bool(self.backboard_api_key)

    @property
    def photon_send_configured(self) -> bool:
        return bool(self.spectrum_bridge_url and self.spectrum_bridge_token)

    def validate_runtime(self) -> None:
        if self.environment == "production":
            if self.jwt_secret in {"", "dev-only-change-me", "replace-with-a-long-random-string"}:
                raise RuntimeError("JWT_SECRET must be set to a unique value in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
