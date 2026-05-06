"""Alembic bootstrap helpers for Jelly Swipe."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

import jellyswipe.db


def build_sqlite_url(db_path: str) -> str:
    path = Path(db_path).expanduser().resolve()
    return f"sqlite:///{path}"


def get_database_url(db_path: str | None = None) -> str:
    if db_path:
        return build_sqlite_url(db_path)

    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    if os.getenv("DB_PATH"):
        return build_sqlite_url(os.environ["DB_PATH"])

    if jellyswipe.db.DB_PATH:
        return build_sqlite_url(jellyswipe.db.DB_PATH)

    default_path = Path(__file__).resolve().parent.parent / "data" / "jellyswipe.db"
    return build_sqlite_url(str(default_path))


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(_alembic_config(database_url or get_database_url()), "head")
