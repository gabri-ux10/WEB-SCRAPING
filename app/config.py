from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/techjobs"
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    usajobs_api_key: str | None = None
    usajobs_email: str | None = None
    jooble_api_key: str | None = None
    request_timeout: float = 30
    max_retries: int = 3
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
