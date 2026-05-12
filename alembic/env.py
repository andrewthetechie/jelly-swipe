from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

from jellyswipe.models.metadata import target_metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _resolve_url() -> str:
    """Resolve database URL for Alembic migrations.

    This function is self-contained and does NOT import AppConfig or
    the application, because Alembic must not depend on application
    configuration that triggers env-var validation or network calls.
    """
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.environ.get("DB_PATH"):
        path = Path(os.environ["DB_PATH"]).expanduser().resolve()
        return f"sqlite:///{path}"
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    path = Path(__file__).resolve().parent.parent / "data" / "jellyswipe.db"
    return f"sqlite:///{path}"


def run_migrations_offline() -> None:
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_resolve_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
