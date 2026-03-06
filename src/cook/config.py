"""Cook configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CookSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    log_level: str = "INFO"


@lru_cache
def get_settings() -> CookSettings:
    return CookSettings()
