"""Dedicated swipe/match mutation service — Phase 39 (D-14).

 Serialized swipe mutations use `BEGIN IMMEDIATE` inside `uow.run_sync(...)`
 without owning commit/rollback. Undo/delete routes recompute room last-match sentinels
 from persisted active match rows (`match_order` / SQLite rowid).
"""

from __future__ import annotations

import json

from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from jellyswipe.config import JELLYFIN_URL
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.room_types import MatchRecord


def _run_query(conn: Connection | object, query: str, params: tuple = ()) -> object:
    if hasattr(conn, "exec_driver_sql"):
        return conn.exec_driver_sql(query, params)
    return conn.execute(query, params)


def _fetchone(conn: Connection | object, query: str, params: tuple = ()) -> dict | None:
    row = _run_query(conn, query, params)
    if hasattr(row, "mappings"):
        mapping = row.mappings().first()
        return dict(mapping) if mapping is not None else None
    record = row.fetchone()
    return dict(record) if record is not None else None


def _execute(conn: Connection | object, query: str, params: tuple = ()) -> None:
    _run_query(conn, query, params)


def _get_cursor(conn: Connection, code: str, user_id: str) -> int:
    room = _fetchone(conn, "SELECT deck_position FROM rooms WHERE pairing_code = ?", (code,))
    if room and room["deck_position"]:
        positions = json.loads(room["deck_position"])
        return int(positions.get(user_id, 0))
    return 0


def _set_cursor(conn: Connection, code: str, user_id: str, position: int) -> None:
    room = _fetchone(conn, "SELECT deck_position FROM rooms WHERE pairing_code = ?", (code,))
    positions = json.loads(room["deck_position"]) if room and room["deck_position"] else {}
    positions[user_id] = position
    _execute(
        conn,
        "UPDATE rooms SET deck_position = ? WHERE pairing_code = ?",
        (json.dumps(positions), code),
    )


def _resolve_movie_meta(movie_data_json: str | None, movie_id: str) -> dict[str, str]:
    try:
        movies = json.loads(movie_data_json or "[]")
        for m in movies:
            if str(m.get("id", "")) == str(movie_id):
                rating = m.get("rating")
                duration = m.get("duration")
                year = m.get("year")
                return {
                    "rating": str(rating) if rating is not None else "",
                    "duration": duration or "",
                    "year": str(year) if year is not None else "",
                }
    except (json.JSONDecodeError, TypeError):
        pass
    return {"rating": "", "duration": "", "year": ""}


def _match_sentinel_rowid(conn: Connection, pairing_code: str, movie_id: str) -> int | None:
    row = _fetchone(
        conn,
        "SELECT MAX(rowid) AS rid FROM matches WHERE room_code = ? AND movie_id = ?",
        (pairing_code, movie_id),
    )
    if not row or row.get("rid") is None:
        return None
    return int(row["rid"])


def _last_match_json(
    *,
    title: str,
    thumb: str,
    movie_id: str,
    meta: dict[str, str],
    deep_link: str,
    sentinel_ts: int | None,
) -> str:
    data = {
        "type": "match",
        "title": title,
        "thumb": thumb,
        "movie_id": movie_id,
        "rating": meta["rating"],
        "duration": meta["duration"],
        "year": meta["year"],
        "deep_link": deep_link,
        "ts": sentinel_ts,
    }
    return json.dumps(data)


def match_record_as_last_match_json(rec: MatchRecord) -> str:
    """Build `rooms.last_match_data` JSON from the newest persisted active match."""

    ts_token = rec.match_order
    payload = {
        "type": "match",
        "title": rec.title,
        "thumb": rec.thumb,
        "movie_id": rec.movie_id,
        "rating": rec.rating or "",
        "duration": rec.duration or "",
        "year": rec.year or "",
        "deep_link": rec.deep_link or "",
        "ts": ts_token if ts_token is not None else 0,
    }
    return json.dumps(payload)


def _sync_run_swipe_transaction(
    sync_session: Session,
    *,
    code: str,
    request_session: dict,
    user_id: str,
    movie_id: str,
    direction: str | None,
    title: str | None,
    thumb: str | None,
) -> tuple[dict, int] | None:
    conn = sync_session.connection()
    raw_connection = conn.connection.driver_connection
    raw_connection.isolation_level = None
    conn.exec_driver_sql("BEGIN IMMEDIATE")

    room_check = _fetchone(
        conn,
        "SELECT 1 FROM rooms WHERE pairing_code = ?",
        (code,),
    )
    if not room_check:
        return ({"error": "Room not found"}, 404)

    _execute(
        conn,
        "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)",
        (code, movie_id, user_id, direction, request_session.get("session_id")),
    )

    current_pos = _get_cursor(conn, code, user_id)
    _set_cursor(conn, code, user_id, current_pos + 1)

    if direction != "right" or title is None or thumb is None:
        return None

    room = _fetchone(conn, "SELECT solo_mode, movie_data FROM rooms WHERE pairing_code = ?", (code,))
    meta = (
        _resolve_movie_meta(room["movie_data"], movie_id)
        if room
        else {"rating": "", "duration": "", "year": ""}
    )
    deep_link = f"{JELLYFIN_URL}/web/#/details?id={movie_id}" if JELLYFIN_URL else ""

    if room and room["solo_mode"]:
        _execute(
            conn,
            'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
            (
                code,
                movie_id,
                title,
                thumb,
                user_id,
                deep_link,
                meta["rating"],
                meta["duration"],
                meta["year"],
            ),
        )
        rid = _match_sentinel_rowid(conn, code, movie_id)
        match_data = _last_match_json(
            title=title,
            thumb=thumb,
            movie_id=movie_id,
            meta=meta,
            deep_link=deep_link,
            sentinel_ts=rid,
        )
        _execute(conn, "UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?", (match_data, code))
        return None

    session_id = request_session.get("session_id")
    if session_id:
        other_swipe = _fetchone(
            conn,
            'SELECT user_id, session_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND (session_id IS NULL OR session_id != ?)',
            (code, movie_id, session_id),
        )
    else:
        other_swipe = _fetchone(
            conn,
            'SELECT user_id, session_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND user_id != ?',
            (code, movie_id, user_id),
        )

    if not other_swipe:
        return None

    _execute(
        conn,
        'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
        (
            code,
            movie_id,
            title,
            thumb,
            user_id,
            deep_link,
            meta["rating"],
            meta["duration"],
            meta["year"],
        ),
    )

    if other_swipe["user_id"] and other_swipe["user_id"] != user_id:
        _execute(
            conn,
            'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
            (
                code,
                movie_id,
                title,
                thumb,
                other_swipe["user_id"],
                deep_link,
                meta["rating"],
                meta["duration"],
                meta["year"],
            ),
        )

    rid = _match_sentinel_rowid(conn, code, movie_id)
    match_data = _last_match_json(
        title=title,
        thumb=thumb,
        movie_id=movie_id,
        meta=meta,
        deep_link=deep_link,
        sentinel_ts=rid,
    )
    _execute(conn, "UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?", (match_data, code))
    return None


class SwipeMatchService:
    """Swipe, undo, and match-delete mutations with parity persistence semantics."""

    async def swipe(
        self,
        *,
        code: str,
        request_session: dict,
        user_id: str,
        movie_id: str,
        direction: str | None,
        title: str | None,
        thumb: str | None,
        uow: DatabaseUnitOfWork,
    ) -> tuple[dict, int] | None:
        return await uow.run_sync(
            _sync_run_swipe_transaction,
            code=code,
            request_session=request_session,
            user_id=user_id,
            movie_id=movie_id,
            direction=direction,
            title=title,
            thumb=thumb,
        )

    async def _recompute_last_match_for_room(self, uow: DatabaseUnitOfWork, pairing_code: str) -> None:
        latest = await uow.matches.latest_active_for_room(pairing_code)
        if latest is None:
            await uow.rooms.set_last_match_data(pairing_code, None)
            return
        await uow.rooms.set_last_match_data(pairing_code, match_record_as_last_match_json(latest))

    async def undo_swipe(
        self,
        *,
        code: str,
        request_session: dict,
        user_id: str,
        movie_id: str,
        uow: DatabaseUnitOfWork,
    ) -> dict:
        await uow.swipes.delete_by_room_movie_session(code, movie_id, request_session.get("session_id"))
        await uow.matches.delete_active_for_room_movie_user(code, movie_id, user_id)
        if await uow.rooms.pairing_code_exists(code):
            await self._recompute_last_match_for_room(uow, code)
        return {"status": "undone"}

    async def delete_match(
        self,
        *,
        movie_id: str,
        user_id: str,
        active_room: str | None,
        uow: DatabaseUnitOfWork,
    ) -> dict:
        await uow.matches.delete_for_user(movie_id, user_id)
        if active_room and await uow.rooms.pairing_code_exists(active_room):
            await self._recompute_last_match_for_room(uow, active_room)
        return {"status": "deleted"}


__all__ = ["SwipeMatchService", "match_record_as_last_match_json"]
