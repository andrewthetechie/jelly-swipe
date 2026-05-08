"""Neutral, sqlite3-free holder for the on-disk SQLite file path.

Alembic URL resolution reads this holder so migrations do not depend on importing
:jellyswipe.db` solely for globals.
"""

from __future__ import annotations

from pathlib import Path


class ApplicationDbPath:
    """Mutable path for migrations, sync adapters, and test bootstrap."""

    __slots__ = ("path",)

    def __init__(self) -> None:
        self.path: str | None = None


application_db_path = ApplicationDbPath()


def default_database_file_path() -> str:
    """Default ``data/jellyswipe.db`` under the repo root."""
    return str(Path(__file__).resolve().parent.parent / "data" / "jellyswipe.db")
