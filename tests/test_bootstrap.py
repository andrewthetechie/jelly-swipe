"""Bootstrap contract tests for migration-first startup."""

from __future__ import annotations

import pytest

from jellyswipe import bootstrap


def test_main_runs_migrations_runtime_and_uvicorn_in_order(monkeypatch):
    calls: list[tuple[str, object]] = []
    sync_url = "sqlite:////tmp/bootstrap.db"
    async_url = "sqlite+aiosqlite:////tmp/bootstrap.db"

    monkeypatch.setattr(
        bootstrap,
        "get_database_url",
        lambda: calls.append(("get_database_url", None)) or sync_url,
    )
    monkeypatch.setattr(
        bootstrap,
        "build_async_database_url",
        lambda database_url: calls.append(("build_async_database_url", database_url)) or async_url,
    )
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
    monkeypatch.setattr(
        bootstrap.uvicorn,
        "run",
        lambda target, host, port: calls.append(("uvicorn.run", (target, host, port))),
    )

    bootstrap.main()

    assert calls == [
        ("get_database_url", None),
        ("build_async_database_url", sync_url),
        ("upgrade_to_head", sync_url),
        ("initialize_runtime", async_url),
        ("uvicorn.run", ("jellyswipe:app", "0.0.0.0", 5005)),
    ]


def test_main_re_raises_migration_failures_before_runtime_or_server(monkeypatch):
    calls: list[tuple[str, object]] = []
    sync_url = "sqlite:////tmp/bootstrap.db"
    async_url = "sqlite+aiosqlite:////tmp/bootstrap.db"

    monkeypatch.setattr(bootstrap, "get_database_url", lambda: sync_url)
    monkeypatch.setattr(bootstrap, "build_async_database_url", lambda database_url: async_url)

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

    assert calls == [("upgrade_to_head", sync_url)]
