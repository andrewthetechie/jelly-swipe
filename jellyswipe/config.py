"""Immutable application configuration built on pydantic-settings.

No import-time side effects. SSRF validation runs only during AppConfig() construction.
"""

from pathlib import Path

from fastapi import Request
from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Immutable application configuration, constructed once at bootstrap.

    Tests construct AppConfig(...) with explicit values, bypassing env vars.
    Production constructs AppConfig() which reads from env vars and .env file.
    """

    jellyfin_url: str
    jellyfin_api_key: str
    tmdb_access_token: str
    session_secret: str
    db_path: str = ""  # empty string = compute default

    @field_validator("jellyfin_url")
    @classmethod
    def _validate_jellyfin_url(cls, v: str) -> str:
        from jellyswipe.ssrf_validator import validate_jellyfin_url

        validate_jellyfin_url(v)
        return v.rstrip("/")

    @computed_field
    @property
    def sync_db_url(self) -> str:
        """Canonical sync sqlite:///... URL for Alembic and runtime."""
        path = Path(
            self.db_path
            or str(Path(__file__).resolve().parent.parent / "data" / "jellyswipe.db")
        ).expanduser().resolve()
        return f"sqlite:///{path}"

    @computed_field
    @property
    def async_db_url(self) -> str:
        """Async sqlite+aiosqlite:///... URL for the FastAPI runtime."""
        return self.sync_db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    model_config = {
        "env_file": ".env",
        "frozen": True,
        "extra": "ignore",
    }


def get_config(request: Request) -> AppConfig:
    """FastAPI dependency that returns the cached AppConfig from app.state."""
    return request.app.state.config


__all__ = ["AppConfig", "get_config"]
