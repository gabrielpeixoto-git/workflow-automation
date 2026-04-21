"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False)

    # Database
    database_url: PostgresDsn = Field(alias="DATABASE_URL")

    # Redis
    redis_url: RedisDsn = Field(alias="REDIS_URL")

    # Celery
    celery_broker_url: str = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(alias="CELERY_RESULT_BACKEND")

    # Security
    secret_key: str = Field(alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    algorithm: str = "HS256"

    # Upload
    upload_dir: Path = Field(default=BASE_DIR / "uploads", alias="UPLOAD_DIR")
    max_upload_size: int = Field(default=10 * 1024 * 1024, alias="MAX_UPLOAD_SIZE")  # 10MB
    allowed_extensions: set[str] = Field(
        default={".csv", ".json", ".xml", ".pdf", ".txt", ".xlsx"},
        alias="ALLOWED_EXTENSIONS",
    )

    # Email
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="noreply@workflow.local", alias="SMTP_FROM")

    # Frontend
    templates_dir: Path = BASE_DIR / "frontend" / "templates"
    static_dir: Path = BASE_DIR / "frontend" / "static"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure upload directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
