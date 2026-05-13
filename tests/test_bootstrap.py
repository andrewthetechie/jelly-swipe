"""Bootstrap contract tests for migration-first startup."""
from __future__ import annotations

import pytest

import jellyswipe
from jellyswipe import bootstrap


def test_main_runs_migrations_runtime_and_uvicorn_in_order(monkeypatch):
    calls: list[tuple[str, object]] = []
    fake_app = object()

    class FakeConfig:
        sync_db_url = "sqlite:////tmp/bootstrap.db"
        async_db_url = "sqlite+aiosqlite:////tmp/bootstrap.db"
        jellyfin_url = "http://test"
        jellyfin_api_key = "k"
        tmdb_access_token = "t"
        session_secret = "s"

    monkeypatch.setattr(bootstrap, "AppConfig", lambda: FakeConfig())
    monkeypatch.setattr(
        bootstrap,
        "upgrade_to_head",
        lambda database_url: calls.append(("upgrade_to_head", database_url)),
    )

    async def fake_initialize_runtime(database_url: str) -> None:
        calls.append(("initialize_runtime", database_url))

    async def fake_dispose_runtime() -> None:
        calls.append(("dispose_runtime", None))

    monkeypatch.setattr(bootstrap, "initialize_runtime", fake_initialize_runtime)
    monkeypatch.setattr(bootstrap, "dispose_runtime", fake_dispose_runtime)
    monkeypatch.setattr(jellyswipe, "create_app", lambda config: fake_app)
    monkeypatch.setattr(
        bootstrap.uvicorn,
        "run",
        lambda target, **kwargs: calls.append(("uvicorn.run", (target, kwargs.get("host"), kwargs.get("port")))),
    )

    bootstrap.main()

    assert calls == [
        ("upgrade_to_head", FakeConfig.sync_db_url),
        ("initialize_runtime", FakeConfig.async_db_url),
        ("uvicorn.run", (fake_app, "0.0.0.0", 5005)),
    ]


def test_main_re_raises_migration_failures_before_runtime_or_server(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeConfig:
        sync_db_url = "sqlite:////tmp/bootstrap.db"
        async_db_url = "sqlite+aiosqlite:////tmp/bootstrap.db"
        jellyfin_url = "http://test"
        jellyfin_api_key = "k"
        tmdb_access_token = "t"
        session_secret = "s"

    monkeypatch.setattr(bootstrap, "AppConfig", lambda: FakeConfig())

    def fail_upgrade(database_url: str) -> None:
        calls.append(("upgrade_to_head", database_url))
        raise RuntimeError("migration failed")

    async def fake_initialize_runtime(database_url: str) -> None:
        calls.append(("initialize_runtime", database_url))

    monkeypatch.setattr(bootstrap, "upgrade_to_head", fail_upgrade)
    monkeypatch.setattr(bootstrap, "initialize_runtime", fake_initialize_runtime)
    monkeypatch.setattr(
        bootstrap.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append(("uvicorn.run", args)),
    )

    with pytest.raises(RuntimeError, match="migration failed"):
        bootstrap.main()

    assert calls == [("upgrade_to_head", FakeConfig.sync_db_url)]
