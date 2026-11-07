"""
App settings loaded from environment variables / .env file.

Usage:
  from config import settings
  settings.MYSQL_HOST
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """All tunables for MySQL, scrape behavior, and file paths."""

    MYSQL_HOST: str = Field(
        default="localhost",
        description="MySQL host name from Hostinger.",
    )

    MYSQL_PORT: int = Field(
        default=3306,
        description="MySQL server port.",
    )

    MYSQL_USER: str = Field(
        default="",
        description="MySQL user name.",
    )

    MYSQL_PASSWORD: str = Field(
        default="",
        description="MySQL password. Keep this only in .env.",
    )

    MYSQL_DATABASE: str = Field(
        default="",
        description="MySQL database name.",
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

    # Keep these false on shared Hostinger plans (connection-per-hour limits).
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Singleton used everywhere else in the project.
settings = Settings()
