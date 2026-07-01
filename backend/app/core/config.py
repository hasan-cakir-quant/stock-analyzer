"""Application configuration loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from env vars or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/stock_analyzer"
    )
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # SEC and Wikimedia both require a descriptive User-Agent that identifies
    # the caller (ideally with a contact email). Override these per deployment.
    sec_edgar_user_agent: str = "Stock Analyzer (personal use) contact@example.com"
    wikipedia_user_agent: str = "Stock Analyzer (personal use) contact@example.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor — reads .env once per process."""
    return Settings()
