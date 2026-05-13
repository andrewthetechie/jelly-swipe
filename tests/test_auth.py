"""Tests for the async auth service boundary."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

import jellyswipe.auth as auth
import jellyswipe.db
import jellyswipe.db_runtime
from jellyswipe.auth_types import AuthRecord
from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import AuthSessionRepository, DatabaseUnitOfWork
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.models.auth_session import AuthSession
from tests.conftest import _bootstrap_temp_db_runtime


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


@pytest.mark.anyio
class TestCreateSession:
    async def test_create_session_inserts_row_sets_session_id_and_cleans_expired_rows(
        self, runtime_sessionmaker
    ):
        old_created_at = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        fresh_created_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        async with runtime_sessionmaker() as session:
            session.add_all(
                [
                    AuthSession(
                        session_id="expired-session",
                        jellyfin_token="expired-token",
                        jellyfin_user_id="expired-user",
                        created_at=old_created_at,
                    ),
                    AuthSession(
                        session_id="fresh-session",
                        jellyfin_token="fresh-token",
                        jellyfin_user_id="fresh-user",
                        created_at=fresh_created_at,
                    ),
                ]
            )
            await session.commit()

        session_dict = {}
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            session_id = await auth.create_session(
                "new-token", "new-user", session_dict, uow
            )
            assert isinstance(session_id, str)
            assert session_id
            assert session_dict["session_id"] == session_id
            await session.commit()

        async with runtime_sessionmaker() as session:
            rows = (
                (
                    await session.execute(
                        select(AuthSession).order_by(AuthSession.session_id)
                    )
                )
                .scalars()
                .all()
            )

        assert len(rows) == 2
        assert {row.session_id for row in rows} == {"fresh-session", session_id}
        created = next(row for row in rows if row.session_id == session_id)
        assert created.jellyfin_token == "new-token"
        assert created.jellyfin_user_id == "new-user"


@pytest.mark.anyio
class TestGetCurrentToken:
    async def test_returns_typed_auth_record_for_valid_session(
        self, runtime_sessionmaker
    ):
        record = AuthRecord(
            session_id="record-session",
            jf_token="record-token",
            user_id="record-user",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        async with runtime_sessionmaker() as session:
            session.add(
                AuthSession(
                    session_id=record.session_id,
                    jellyfin_token=record.jf_token,
                    jellyfin_user_id=record.user_id,
                    created_at=record.created_at,
                )
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            current = await auth.get_current_token(
                {"session_id": record.session_id}, uow
            )

        assert current == record

    async def test_returns_none_for_missing_session_id_or_missing_row(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            assert await auth.get_current_token({}, uow) is None
            assert await auth.get_current_token({"session_id": "missing"}, uow) is None


@pytest.mark.anyio
class TestDestroySession:
    async def test_destroy_session_clears_all_local_state_and_deletes_row(
        self, runtime_sessionmaker
    ):
        record = AuthRecord(
            session_id="destroy-session",
            jf_token="destroy-token",
            user_id="destroy-user",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        async with runtime_sessionmaker() as session:
            session.add(
                AuthSession(
                    session_id=record.session_id,
                    jellyfin_token=record.jf_token,
                    jellyfin_user_id=record.user_id,
                    created_at=record.created_at,
                )
            )
            await session.commit()

        session_dict = {
            "session_id": record.session_id,
            "active_room": "ROOM1",
            "solo_mode": True,
        }
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await auth.destroy_session(session_dict, uow)
            await session.commit()

        assert session_dict == {}

        async with runtime_sessionmaker() as session:
            persisted = (
                await session.execute(
                    select(AuthSession).where(
                        AuthSession.session_id == record.session_id
                    )
                )
            ).scalar_one_or_none()
        assert persisted is None

    async def test_destroy_session_swallows_delete_failures_after_clearing_local_state(
        self, runtime_sessionmaker, monkeypatch
    ):
        async def blow_up(self, session_id: str) -> int:
            raise RuntimeError(f"delete failed for {session_id}")

        session_dict = {
            "session_id": "broken-session",
            "active_room": "ROOM1",
            "solo_mode": True,
        }
        monkeypatch.setattr(AuthSessionRepository, "delete_by_session_id", blow_up)

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            with patch.object(auth._logger, "error") as mock_error:
                await auth.destroy_session(session_dict, uow)

        assert session_dict == {}
        mock_error.assert_called_once()
        assert mock_error.call_args.args[0] == "auth_session_delete_failed"


def test_shared_bootstrap_reinitializes_runtime_for_distinct_temp_dbs(tmp_path):
    first_db_path = str(tmp_path / "first.db")
    second_db_path = str(tmp_path / "second.db")

    try:
        first_bootstrap = _bootstrap_temp_db_runtime(first_db_path)
        assert (
            jellyswipe.db_runtime.RUNTIME_DATABASE_URL
            == first_bootstrap["runtime_database_url"]
        )

        asyncio.run(jellyswipe.db_runtime.dispose_runtime())

        second_bootstrap = _bootstrap_temp_db_runtime(second_db_path)
        assert (
            jellyswipe.db_runtime.RUNTIME_DATABASE_URL
            == second_bootstrap["runtime_database_url"]
        )
        assert (
            second_bootstrap["runtime_database_url"]
            != first_bootstrap["runtime_database_url"]
        )

        asyncio.run(jellyswipe.db_runtime.dispose_runtime())
    finally:
        pass
