"""
App settings loaded from environment variables / .env file.

Usage:
  from config import settings
    settings.POSTGRES_HOST
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """All tunables for PostgreSQL, scrape behavior, and file paths."""

    DATABASE_URL: str = Field(
        default="",
        description="Optional PostgreSQL connection string; takes precedence over POSTGRES_* fields.",
    )

    POSTGRES_HOST: str = Field(
        default="localhost",
        description="PostgreSQL host name.",
    )

    POSTGRES_PORT: int = Field(
        default=5432,
        description="PostgreSQL server port.",
    )

    POSTGRES_USER: str = Field(
        default="",
        description="PostgreSQL user name.",
    )

    POSTGRES_PASSWORD: str = Field(
        default="",
        description="PostgreSQL password. Keep this only in .env.",
    )

    POSTGRES_DATABASE: str = Field(
        default="",
        description="PostgreSQL database name.",
    )

    POSTGRES_SSLMODE: str = Field(
        default="prefer",
        description="PostgreSQL SSL mode for hosted database connections.",
    )

    SCRAPES_DIR: str = Field(
        default=str(BASE_DIR / "data" / "scrapes"),
        description="Root folder for timestamped scrape session data.",
    )

    EXCEL_EXPORT_FILE: str = Field(
        default=str(BASE_DIR / "data" / "fd_rates_export.xlsx"),
        description="Temporary Excel export generated from the database.",
    )

    ENABLE_SCHEDULER: bool = Field(
        default=False,
        description="Enable APScheduler background jobs (daily scrapes later).",
    )

    # Keep these false on hosted plans with connection limits.
    INIT_DB_ON_STARTUP: bool = Field(
        default=False,
        description="Run schema migration on app startup (off by default for shared hosting).",
    )

    SCRAPE_ON_STARTUP: bool = Field(
        default=False,
        description="Run a full bank scrape when the app starts.",
    )

    SCRAPE_CRON: str = Field(
        default="0 2 * * *",
        description="Cron expression for daily scrape (when scheduler is enabled).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton used everywhere else in the project.
settings = Settings()
