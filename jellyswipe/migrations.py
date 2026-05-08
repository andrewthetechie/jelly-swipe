"""Alembic/bootstrap helpers using a canonical sync SQLite URL contract.

`DATABASE_URL` is treated as the canonical sync SQLite target for this phase.
Alembic and bootstrap always consume the sync `sqlite:///...` form, while the
async runtime derives its own `sqlite+aiosqlite:///...` URL from this module.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from jellyswipe.db_paths import application_db_path, default_database_file_path

_SYNC_SQLITE_PREFIX = "sqlite:///"
_ASYNC_SQLITE_PREFIX = "sqlite+aiosqlite:///"


def build_sqlite_url(db_path: str) -> str:
    path = Path(db_path).expanduser().resolve()
    return f"{_SYNC_SQLITE_PREFIX}{path}"


def normalize_sync_database_url(database_url: str) -> str:
    """Normalize runtime URLs back to the canonical sync SQLite form."""
    if database_url.startswith(_ASYNC_SQLITE_PREFIX):
        return database_url.replace(_ASYNC_SQLITE_PREFIX, _SYNC_SQLITE_PREFIX, 1)
    if database_url.startswith(_SYNC_SQLITE_PREFIX):
        return database_url
    raise ValueError(
        "DATABASE_URL must use a SQLite database URL in sync or sqlite+aiosqlite form"
    )


def get_database_url(db_path: str | None = None) -> str:
    if db_path:
        return normalize_sync_database_url(build_sqlite_url(db_path))

    if os.getenv("DATABASE_URL"):
        return normalize_sync_database_url(os.environ["DATABASE_URL"])

    if os.getenv("DB_PATH"):
        return normalize_sync_database_url(build_sqlite_url(os.environ["DB_PATH"]))

    if application_db_path.path:
        return normalize_sync_database_url(build_sqlite_url(application_db_path.path))

    return normalize_sync_database_url(build_sqlite_url(default_database_file_path()))


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(
        _alembic_config(normalize_sync_database_url(database_url or get_database_url())),
        "head",
    )
