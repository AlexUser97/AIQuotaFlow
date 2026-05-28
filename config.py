from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite+aiosqlite:///data/aiquotaflow.db"
    LOG_LEVEL: str = "INFO"
    ADMIN_IDS: list[int] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def sync_database_url(self) -> str:
        """Synchronous SQLAlchemy URL for APScheduler jobstore."""
        return self.DATABASE_URL.replace("+aiosqlite", "")


settings = Settings()
