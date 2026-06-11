"""Application settings loaded from environment variables.

Uses pydantic-settings for type-safe, validated configuration. A single cached
``Settings`` instance is exposed via :func:`get_settings` and the module-level
``settings`` object.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Application -----
    app_env: Literal["production", "staging", "development"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    tz: str = "UTC"

    # ----- Telegram -----
    bot_token: str = Field(..., min_length=10)
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    log_channel_id: int | None = None

    webhook_url: str | None = None
    webhook_path: str = "/webhook"
    webhook_secret: str = "change-me"
    webapp_host: str = "0.0.0.0"
    webapp_port: int = 8080

    # ----- PostgreSQL -----
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "dicebot"
    postgres_password: str = "dicebot"
    postgres_db: str = "dicebot"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_echo: bool = False

    # ----- Redis -----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # ----- Economy -----
    starting_balance: int = 1000
    daily_reward: int = 250
    weekly_reward: int = 1500
    referral_reward: int = 500
    min_bet: int = 10
    max_bet: int = 1_000_000
    house_edge: float = 0.02

    # ----- Anti-cheat / rate limiting -----
    rate_limit_per_second: int = 3
    battle_cooldown_seconds: int = 3
    max_daily_battles: int = 2000

    # ----- Runtime -----
    # Run the APScheduler in this process. In multi-replica deployments only ONE
    # replica should set this to true to avoid duplicate season rollovers.
    run_scheduler: bool = True

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        """Allow ADMIN_IDS to be a comma-separated string, an int, or a list."""
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple)):
            return [int(v) for v in value]
        raise ValueError("admin_ids must be a comma-separated string or list of ints")

    @field_validator("redis_password", "webhook_url", "log_channel_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver)."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Sync DSN (psycopg/asyncpg) used by Alembic migrations."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg2",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()
