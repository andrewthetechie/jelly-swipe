# Phase 39: Room, Swipe, Match, and SSE Persistence Conversion - Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 14
**Analogs found:** 14 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `jellyswipe/repositories/rooms.py` | repository | CRUD | `jellyswipe/db_uow.py` + `jellyswipe/routers/rooms.py` | role-match |
| `jellyswipe/repositories/swipes.py` | repository | CRUD | `jellyswipe/db_uow.py` + `jellyswipe/routers/rooms.py` | role-match |
| `jellyswipe/repositories/matches.py` | repository | CRUD | `jellyswipe/db_uow.py` + `jellyswipe/routers/rooms.py` | role-match |
| `jellyswipe/services/room_lifecycle.py` | service | request-response | `jellyswipe/auth.py` + `jellyswipe/routers/rooms.py` | role-match |
| `jellyswipe/services/swipe_match.py` | service | CRUD | `jellyswipe/routers/rooms.py::_run_swipe_transaction` + `jellyswipe/auth.py` | data-flow-match |
| `jellyswipe/db_uow.py` | store | CRUD | `jellyswipe/db_uow.py` | exact |
| `jellyswipe/routers/rooms.py` | route | request-response + streaming | `jellyswipe/routers/rooms.py` + `jellyswipe/routers/auth.py` | exact |
| `tests/conftest.py` | config | batch | `tests/conftest.py` | exact |
| `tests/test_routes_room.py` | test | request-response | `tests/test_routes_room.py` | exact |
| `tests/test_routes_sse.py` | test | streaming | `tests/test_routes_sse.py` | exact |
| `tests/test_route_authorization.py` | test | request-response | `tests/test_route_authorization.py` | exact |
| `tests/test_room_lifecycle.py` | test | request-response | `tests/test_auth.py` + `tests/conftest.py` | role-match |
| `tests/test_swipe_match.py` | test | CRUD | `tests/test_dependencies.py` + `tests/test_route_authorization.py` | role-match |
| `tests/test_repositories.py` | test | CRUD | `tests/test_auth.py` + `tests/conftest.py` | role-match |

## Pattern Assignments

### `jellyswipe/repositories/rooms.py` (repository, CRUD)

**Analog:** `jellyswipe/db_uow.py` and room-read helpers in `jellyswipe/routers/rooms.py`

**Repository class shape** from `jellyswipe/db_uow.py` lines 17-58:
```python
class AuthSessionRepository:
    """Repository for auth session maintenance queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_expired(self, cutoff_iso: str) -> int:
        result = await self._session.execute(
            text("DELETE FROM auth_sessions WHERE created_at < :cutoff_iso"),
            {"cutoff_iso": cutoff_iso},
        )
        return result.rowcount or 0
```

**Room cursor/status projection logic** from `jellyswipe/routers/rooms.py` lines 85-103 and 447-452:
```python
def _get_cursor(conn: Connection, code, user_id):
    room = _fetchone(conn, 'SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,))
    if room and room['deck_position']:
        positions = json.loads(room['deck_position'])
        return positions.get(user_id, 0)
    return 0


def _set_cursor(conn: Connection, code, user_id, position):
    room = _fetchone(conn, 'SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,))
    positions = json.loads(room['deck_position']) if room and room['deck_position'] else {}
    positions[user_id] = position
    _execute(
        conn,
        'UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
        (json.dumps(positions), code),
    )


room = conn.execute('SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
if room:
    last_match = json.loads(room['last_match_data']) if room['last_match_data'] else None
    return {'ready': bool(room['ready']), 'genre': room['current_genre'], 'solo': bool(room['solo_mode']), 'last_match': last_match}
return {'ready': False}
```

**Model fields to preserve** from `jellyswipe/models/room.py` lines 15-36:
```python
class Room(Base):
    __tablename__ = "rooms"

    pairing_code: Mapped[str] = mapped_column(Text, primary_key=True)
    movie_data: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    ready: Mapped[int] = mapped_column(nullable=False, server_default="0")
    current_genre: Mapped[str] = mapped_column(Text, nullable=False, server_default="All")
    solo_mode: Mapped[int] = mapped_column(nullable=False, server_default="0")
    last_match_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_order: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Use for Phase 39:** keep the repository async and narrow. Return typed room state for create/join/quit/genre/deck/status operations, but keep transaction sequencing and session mutation in `room_lifecycle.py`.

---

### `jellyswipe/repositories/swipes.py` (repository, CRUD)

**Analog:** `jellyswipe/db_uow.py` and the serialized swipe bridge in `jellyswipe/routers/rooms.py`

**Async repository surface** from `jellyswipe/db_uow.py` lines 61-74:
```python
class SwipeRepository:
    """Repository for swipe maintenance queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_orphans(self) -> int:
        result = await self._session.execute(
            text(
                "DELETE FROM swipes "
                "WHERE room_code NOT IN (SELECT pairing_code FROM rooms)"
            )
        )
        return result.rowcount or 0
```

**Serialized write pattern** from `jellyswipe/routers/rooms.py` lines 143-166:
```python
conn = sync_session.connection()
raw_connection = conn.connection.driver_connection
raw_connection.isolation_level = None
conn.exec_driver_sql('BEGIN IMMEDIATE')

room_check = _fetchone(
    conn,
    'SELECT 1 FROM rooms WHERE pairing_code = ?',
    (code,),
)
if not room_check:
    return ({'error': 'Room not found'}, 404)

_execute(
    conn,
    'INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)',
    (code, movie_id, user_id, direction, request_session.get('session_id')),
)
```

**Schema/index expectations** from `jellyswipe/models/swipe.py` lines 15-40:
```python
class Swipe(Base):
    __tablename__ = "swipes"
    __table_args__ = (
        Index("ix_swipes_room_movie_direction", "room_code", "movie_id", "direction"),
        Index("ix_swipes_room_movie_session", "room_code", "movie_id", "session_id"),
    )

    room_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("rooms.pairing_code", ondelete="CASCADE"),
        primary_key=True,
    )
    movie_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("auth_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
```

**Use for Phase 39:** split normal async swipe reads/deletes into this repository, but keep the critical `BEGIN IMMEDIATE` sync bridge callable here or adjacent so `SwipeMatchService` can call it through `uow.run_sync(...)`.

---

### `jellyswipe/repositories/matches.py` (repository, CRUD)

**Analog:** `jellyswipe/db_uow.py` and match-query blocks in `jellyswipe/routers/rooms.py`

**Active/history query shape** from `jellyswipe/routers/rooms.py` lines 348-359:
```python
code = request.session.get('active_room')
view = request.query_params.get('view')

with get_db_closing() as conn:
    if view == 'history':
        rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE status = "archived" AND user_id = ?', (user.user_id,)).fetchall()
    else:
        rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE room_code = ? AND status = "active" AND user_id = ?', (code, user.user_id)).fetchall()
    return [dict(row) for row in rows]
```

**Archive/delete semantics** from `jellyswipe/routers/rooms.py` lines 365-387:
```python
conn.execute('DELETE FROM rooms WHERE pairing_code = ?', (code,))
conn.execute('DELETE FROM swipes WHERE room_code = ?', (code,))
conn.execute('UPDATE matches SET status = "archived", room_code = "HISTORY" WHERE room_code = ? AND status = "active"', (code,))


conn.execute('DELETE FROM matches WHERE movie_id = ? AND user_id = ?', (mid, user.user_id))
```

**Schema/uniqueness rules** from `jellyswipe/models/match.py` lines 14-39:
```python
class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("room_code", "movie_id", "user_id", name="uq_matches_room_movie_user"),
        Index("ix_matches_status_user_id", "status", "user_id"),
    )

    room_code: Mapped[str] = mapped_column(Text, nullable=False)
    movie_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    thumb: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
```

**Use for Phase 39:** keep history/archive/delete logic in this repository. `SwipeMatchService` should orchestrate when those methods are called and when `rooms.last_match_data` must be recomputed.

---

### `jellyswipe/services/room_lifecycle.py` (service, request-response)

**Analog:** `jellyswipe/auth.py` for service shape and `jellyswipe/routers/rooms.py` for room lifecycle semantics

**Thin async service pattern** from `jellyswipe/auth.py` lines 22-42 and 71-91:
```python
async def create_session(
    jf_token: str, jf_user_id: str, session_dict: dict, uow: DatabaseUnitOfWork
) -> str:
    now = datetime.now(timezone.utc)
    session_id = secrets.token_urlsafe(32)
    created_at = now.isoformat()
    cutoff_iso = (now - timedelta(days=14)).isoformat()

    await uow.auth_sessions.delete_expired(cutoff_iso)
    await uow.auth_sessions.insert(
        AuthRecord(
            session_id=session_id,
            jf_token=jf_token,
            user_id=jf_user_id,
            created_at=created_at,
        )
    )

    session_dict["session_id"] = session_id
    return session_id


async def resolve_active_room(session_dict: dict, uow: DatabaseUnitOfWork) -> str | None:
    active_room = session_dict.get("active_room")
    if active_room is None:
        return None
    ...
    session_dict.pop("active_room", None)
    session_dict.pop("solo_mode", None)
    return None
```

**Room lifecycle semantics** from `jellyswipe/routers/rooms.py` lines 235-298 and 427-452:
```python
for _ in range(10):
    pairing_code = str(secrets.randbelow(9000) + 1000)
    with get_db_closing() as conn:
        existing = conn.execute(
            'SELECT 1 FROM rooms WHERE pairing_code = ?', (pairing_code,)
        ).fetchone()
        if not existing:
            movie_list = get_provider().fetch_deck()
            conn.execute('INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                         (pairing_code, json.dumps(movie_list), 0, 'All', 0))
            conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                         (json.dumps({user.user_id: 0}), pairing_code))
            request.session['active_room'] = pairing_code
            request.session['solo_mode'] = False
            return {'pairing_code': pairing_code}


room = conn.execute('SELECT * FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
if room:
    conn.execute('UPDATE rooms SET ready = 1 WHERE pairing_code = ?', (code,))
    ...
    request.session['active_room'] = code
    request.session['solo_mode'] = False
    return {'status': 'success'}


room = conn.execute('SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
if room:
    last_match = json.loads(room['last_match_data']) if room['last_match_data'] else None
    return {'ready': bool(room['ready']), 'genre': room['current_genre'], 'solo': bool(room['solo_mode']), 'last_match': last_match}
return {'ready': False}
```

**Use for Phase 39:** keep provider calls, pairing-code generation, room/session state mutation, and graceful missing-room behavior in this service. Routes should only decode HTTP input and apply the returned session changes.

---

### `jellyswipe/services/swipe_match.py` (service, CRUD)

**Analog:** `_run_swipe_transaction` in `jellyswipe/routers/rooms.py` plus the async service/UoW pattern in `jellyswipe/auth.py`

**Atomic swipe/match unit** from `jellyswipe/routers/rooms.py` lines 125-228:
```python
def _run_swipe_transaction(
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
    ...
    conn.exec_driver_sql('BEGIN IMMEDIATE')
    ...
    _execute(
        conn,
        'INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)',
        (code, movie_id, user_id, direction, request_session.get('session_id')),
    )

    current_pos = _get_cursor(conn, code, user_id)
    _set_cursor(conn, code, user_id, current_pos + 1)
    ...
    _execute(conn, 'UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))
    return None
```

**Async bridge call site** from `jellyswipe/routers/rooms.py` lines 331-345:
```python
result = await uow.run_sync(
    _run_swipe_transaction,
    code=code,
    request_session=request.session,
    user_id=user.user_id,
    movie_id=mid,
    direction=data.get('direction'),
    title=title,
    thumb=thumb,
)
if result is not None:
    body, status_code = result
    return XSSSafeJSONResponse(content=body, status_code=status_code)

return {'accepted': True}
```

**Undo/delete semantics to preserve** from `jellyswipe/routers/rooms.py` lines 390-404:
```python
conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND session_id = ?', (code, mid, request.session.get('session_id')))
conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND user_id = ?', (code, mid, user.user_id))
return {'status': 'undone'}
```

**Use for Phase 39:** this service owns transaction coordination across room, swipe, and match repositories. Keep provider metadata resolution outside the serialized lock window when possible, and keep the bridge callable free of final commit/rollback.

---

### `jellyswipe/db_uow.py` (store, CRUD)

**Analog:** `jellyswipe/db_uow.py`

**Repository attachment pattern** from `jellyswipe/db_uow.py` lines 77-93:
```python
class DatabaseUnitOfWork:
    """Typed async unit-of-work facade around one AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth_sessions = AuthSessionRepository(session)
        self.swipes = SwipeRepository(session)

    async def run_sync(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run legacy sync work on the managed session connection.

        The sync callable may issue `BEGIN IMMEDIATE` or other SQLite statements,
        but it must not own the final COMMIT or ROLLBACK. The dependency boundary
        remains the single owner of transaction completion for this session.
        """

        return await self.session.run_sync(lambda sync_session: fn(sync_session, *args, **kwargs))
```

**Use for Phase 39:** extend this file instead of creating a second UoW abstraction. Add `rooms`, `swipes`, and `matches` repositories here, and preserve `run_sync()` exactly as the transaction bridge used by swipe mutations.

---

### `jellyswipe/routers/rooms.py` (route, request-response + streaming)

**Analog:** `jellyswipe/routers/rooms.py` with DI style from `jellyswipe/routers/auth.py`

**DI import pattern** from `jellyswipe/routers/auth.py` lines 13-20:
```python
from jellyswipe.dependencies import (
    AuthUser,
    DBUoW,
    check_rate_limit,
    get_provider,
    require_auth,
)
```

**Route error-response helper** from `jellyswipe/routers/rooms.py` lines 39-62:
```python
def make_error_response(message: str, status_code: int, request: Request, extra_fields: dict = None) -> XSSSafeJSONResponse:
    if status_code >= 500:
        message = 'Internal server error'
    body = {'error': message}
    body['request_id'] = getattr(request.state, 'request_id', 'unknown')
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)
```

**Controller-thin target shape** from `jellyswipe/routers/auth.py` lines 110-121:
```python
@auth_router.get('/me')
async def get_me(request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)):
    active_room = await resolve_active_room(request.session, uow)
    info = get_provider().server_info()
    return {
        'userId': user.user_id,
        'displayName': user.user_id,
        'serverName': info.get('name', ''),
        'serverId': info.get('machineIdentifier', ''),
        'activeRoom': active_room,
    }
```

**SSE generator pattern to preserve** from `jellyswipe/routers/rooms.py` lines 462-536:
```python
async def generate():
    last_genre = None
    last_ready = None
    last_match_ts = None
    POLL = 1.5
    TIMEOUT = 3600
    _last_event_time = time.time()
    ...
    if await request.is_disconnected():
        break
    ...
    if row is None:
        yield {"data": json.dumps({'closed': True})}
        return
    ...
    elif time.time() - _last_event_time >= 15:
        yield {"comment": "ping"}
        _last_event_time = time.time()
    ...
return EventSourceResponse(generate(), headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
```

**Use for Phase 39:** preserve paths, response bodies, and session side effects. Only move DB work out into services/repositories; keep the SSE endpoint local to this router unless a helper is strictly stream-focused and does not change the HTTP contract.

---

### `tests/conftest.py` (config, batch)

**Analog:** `tests/conftest.py`

**Runtime bootstrap fixture** from `tests/conftest.py` lines 120-138:
```python
def _bootstrap_temp_db_runtime(db_path, monkeypatch):
    """Provision one temp database through Alembic plus the async runtime path."""
    import jellyswipe.db

    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    asyncio.run(initialize_runtime(runtime_database_url))
```

**App fixture override pattern** from `tests/conftest.py` lines 236-287:
```python
@pytest.fixture
def app(db_path, monkeypatch):
    ...
    fast_app = create_app(test_config=test_config)

    fast_app.dependency_overrides[require_auth] = lambda: AuthUser(
        jf_token="valid-token", user_id="verified-user"
    )
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider
    ...
    yield fast_app
    _dispose_test_runtime()
    fast_app.dependency_overrides.clear()
```

**Real-auth fixture pattern** from `tests/conftest.py` lines 302-352:
```python
@pytest.fixture
def app_real_auth(db_path, monkeypatch):
    ...
    fast_app = create_app(test_config=test_config)
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider
    ...
    yield fast_app
    _dispose_test_runtime()
    fast_app.dependency_overrides.clear()
```

**Use for Phase 39:** extend this file only if the new service/repository tests need a shared async sessionmaker or helper seed fixture. Reuse `_bootstrap_temp_db_runtime()` instead of inventing new DB bootstrap code.

---

### `tests/test_routes_room.py` (test, request-response)

**Analog:** `tests/test_routes_room.py`

**Route contract style** from `tests/test_routes_room.py` lines 63-106:
```python
def test_room_create_returns_pairing_code(client, app):
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    data = response.json()
    assert "pairing_code" in data
    code = data["pairing_code"]
    assert len(str(code)) == 4
    assert str(code).isdigit()
```

**Room lifecycle parity checks** from `tests/test_routes_room.py` lines 200-270:
```python
response = client.post("/room/TEST1/quit")
assert response.status_code == 200
assert response.json() == {"status": "session_ended"}
...
assert row["status"] == "archived"
assert row["room_code"] == "HISTORY"
```

**Swipe parity checks** from `tests/test_routes_room.py` lines 349-485:
```python
response = client.post(
    "/room/TEST1/swipe",
    json={"movie_id": "m1", "direction": "right"},
)
assert response.status_code == 200
assert response.json() == {"accepted": True}
...
match_data = json.loads(row["last_match_data"])
assert match_data["type"] == "match"
assert "ts" in match_data
```

**Use for Phase 39:** keep this file as the basic controller contract suite. Add or update cases here only when route-level room behavior changes under the persistence refactor.

---

### `tests/test_routes_sse.py` (test, streaming)

**Analog:** `tests/test_routes_sse.py`

**Header and first-snapshot contract** from `tests/test_routes_sse.py` lines 149-173 and 197-220:
```python
response = client.get("/room/TEST1/stream")
_ = response.content

assert response.headers.get("content-type", "").startswith("text/event-stream")
assert response.headers["Cache-Control"] == "no-cache"
assert response.headers["X-Accel-Buffering"] == "no"


response = client.get("/room/TEST1/stream")
data = response.text
assert '"ready": false' in data
assert '"solo": false' in data
assert '"genre": "All"' in data
```

**Dedup/heartbeat/disconnect contract** from `tests/test_routes_sse.py` lines 222-250, 400-445, and 511-587:
```python
ready_count = sum(1 for e in events if '"ready"' in e)
genre_count = sum(1 for e in events if '"genre"' in e)
assert ready_count == 1
assert genre_count == 1


assert ": ping" in data


assert db_execute_count[0] == 1
assert response.status_code == 200
assert response.headers.get("content-type", "").startswith("text/event-stream")
```

**Cancellation/cleanup contract** from `tests/test_routes_sse.py` lines 651-738:
```python
async def drive_generator():
    try:
        async for _ in generator:
            pass
    except (asyncio.CancelledError, Exception) as exc:
        if isinstance(exc, asyncio.CancelledError):
            cancelled_error_propagated[0] = True
        else:
            raise

assert cancelled_error_propagated[0]
assert close_called[0]
```

**Use for Phase 39:** keep this file as the SSE parity gate. New async polling must satisfy the same snapshot, closed-room, heartbeat, disconnect, and cleanup behavior.

---

### `tests/test_route_authorization.py` (test, request-response)

**Analog:** `tests/test_route_authorization.py`

**Real-auth session fixture pattern** from `tests/test_route_authorization.py` lines 18-36:
```python
def _set_session(client, db_connection, secret_key, *, active_room: str = "ROOM1", authenticated: bool = True):
    if authenticated:
        session_id = "test-session-" + secrets.token_hex(8)
        db_connection.execute(
            "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "valid-token", "verified-user", datetime.now(timezone.utc).isoformat())
        )
        db_connection.commit()
        set_session_cookie(
            client,
            {"session_id": session_id, "active_room": active_room},
            secret_key
        )
```

**Enriched match/deep-link assertions** from `tests/test_route_authorization.py` lines 455-542:
```python
row = db_connection.execute(
    "SELECT deep_link FROM matches WHERE room_code = ? AND movie_id = ?",
    ("ROOM1", "movie-1"),
).fetchone()
assert row is not None
assert "/web/#/details?id=movie-1" in row["deep_link"]


row = db_connection.execute(
    "SELECT last_match_data FROM rooms WHERE pairing_code = ?",
    ("ROOM1",),
).fetchone()
data = json.loads(row["last_match_data"])
assert data["rating"] == "8.5"
assert data["duration"] == "2h 15m"
assert data["year"] == "2024"
assert "/web/#/details?id=movie-1" in data["deep_link"]
```

**Stale-session and active-room compatibility checks** from `tests/test_route_authorization.py` lines 662-675, 717-727, and 953-977:
```python
resp = client_real_auth.get("/me")
assert resp.status_code == 401
assert resp.json() == {"detail": "Authentication required"}
assert client_real_auth.cookies.get("session") is None


resp2 = client_real_auth.get('/me')
assert resp2.status_code == 200
assert resp2.json()['activeRoom'] == code


resp = client_real_auth.get('/me')
assert resp.status_code == 200
assert resp.json()['activeRoom'] is None
...
resp = client_real_auth.post(f'/room/{code}/quit')
...
assert resp.json()['activeRoom'] is None
```

**Use for Phase 39:** keep or extend this file for real-auth room/session compatibility edges, especially stale-room cleanup and active-room transitions that route tests with auth overrides do not exercise.

---

### `tests/test_room_lifecycle.py` (test, request-response)

**Analog:** `tests/test_auth.py` and `tests/conftest.py`

**Async service test harness** from `tests/test_auth.py` lines 36-48 and 79-97:
```python
@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)
    ...
    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


async with runtime_sessionmaker() as session:
    uow = DatabaseUnitOfWork(session)
    session_id = await auth.create_session("new-token", "new-user", session_dict, uow)
    assert isinstance(session_id, str)
    assert session_dict["session_id"] == session_id
    await session.commit()
```

**Use for Phase 39:** mirror this style for service-only tests that call `RoomLifecycleService` directly with a real `DatabaseUnitOfWork`, assert returned data, and then verify DB state with a second session.

---

### `tests/test_swipe_match.py` (test, CRUD)

**Analog:** `tests/test_dependencies.py` and `tests/test_route_authorization.py`

**Bridge/transaction test pattern** from `tests/test_dependencies.py` lines 165-210:
```python
generator = get_db_uow()
uow = await generator.__anext__()

assert isinstance(uow, DatabaseUnitOfWork)

await uow.run_sync(_begin_immediate_insert, "committed")

with pytest.raises(StopAsyncIteration):
    await generator.__anext__()

assert counts == {"commit": 1, "rollback": 0, "close": 1}
```

**Swipe/match semantic assertions** from `tests/test_route_authorization.py` lines 521-542 and 624-635:
```python
row = db_connection.execute(
    "SELECT last_match_data FROM rooms WHERE pairing_code = ?",
    ("ROOM1",),
).fetchone()
data = json.loads(row["last_match_data"])
assert data["type"] == "match"
assert data["movie_id"] == "movie-1"
assert "ts" in data


rows = db_connection.execute(
    "SELECT user_id FROM matches WHERE room_code = ? AND movie_id = ?",
    (code, "movie-1"),
).fetchall()
assert [row["user_id"] for row in rows] == ["verified-user"]
assert len(first_matches.json()) == 1
assert len(second_matches.json()) == 1
```

**Use for Phase 39:** direct-service tests here should cover swipe atomicity, deck cursor advance, solo-vs-shared matching, undo/delete recomputation, and rollback behavior after bridge work.

---

### `tests/test_repositories.py` (test, CRUD)

**Analog:** `tests/test_auth.py`

**Repository verification pattern** from `tests/test_auth.py` lines 52-97 and 133-168:
```python
async with runtime_sessionmaker() as session:
    session.add_all([...])
    await session.commit()

async with runtime_sessionmaker() as session:
    uow = DatabaseUnitOfWork(session)
    session_id = await auth.create_session("new-token", "new-user", session_dict, uow)
    await session.commit()

async with runtime_sessionmaker() as session:
    rows = (
        await session.execute(select(AuthSession).order_by(AuthSession.session_id))
    ).scalars().all()

assert len(rows) == 2
...
persisted = (
    await session.execute(
        select(AuthSession).where(AuthSession.session_id == record.session_id)
    )
).scalar_one_or_none()
assert persisted is None
```

**Use for Phase 39:** keep repository tests narrow and state-based. Insert or mutate through repository methods, commit, then verify persisted `Room`, `Swipe`, and `Match` rows directly with ORM/Core queries in a fresh session.

---

## Shared Patterns

### Request-Scoped UoW Ownership
**Source:** `jellyswipe/dependencies.py` lines 32-45
**Apply to:** `jellyswipe/routers/rooms.py`, `jellyswipe/services/room_lifecycle.py`, `jellyswipe/services/swipe_match.py`
```python
async def get_db_uow():
    """Yield a request-scoped async unit of work."""
    session = get_sessionmaker()()
    try:
        yield DatabaseUnitOfWork(session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


DBUoW = Annotated[DatabaseUnitOfWork, Depends(get_db_uow, scope="function")]
```

### Stale Room Session Cleanup
**Source:** `jellyswipe/auth.py` lines 71-91
**Apply to:** `room_lifecycle.py` return contracts and any route/session cleanup on missing rooms
```python
async def resolve_active_room(session_dict: dict, uow: DatabaseUnitOfWork) -> str | None:
    active_room = session_dict.get("active_room")
    if active_room is None:
        return None
    ...
    if await uow.run_sync(_room_exists, active_room):
        return active_room

    session_dict.pop("active_room", None)
    session_dict.pop("solo_mode", None)
    return None
```

### Serialized Swipe Bridge
**Source:** `jellyswipe/db_uow.py` lines 85-93 and `jellyswipe/routers/rooms.py` lines 143-166
**Apply to:** `jellyswipe/services/swipe_match.py`, `jellyswipe/repositories/swipes.py`
```python
async def run_sync(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    return await self.session.run_sync(lambda sync_session: fn(sync_session, *args, **kwargs))


raw_connection = conn.connection.driver_connection
raw_connection.isolation_level = None
conn.exec_driver_sql('BEGIN IMMEDIATE')
```

### Stream-Local Session Access
**Source:** `jellyswipe/db_runtime.py` lines 89-100 and `jellyswipe/routers/rooms.py` lines 462-536
**Apply to:** SSE polling code only
```python
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if RUNTIME_SESSIONMAKER is None:
        raise RuntimeError(
            "Async database runtime is not initialized. Call initialize_runtime() before requesting sessions."
        )
    return RUNTIME_SESSIONMAKER


async def generate():
    ...
    if await request.is_disconnected():
        break
    ...
    elif time.time() - _last_event_time >= 15:
        yield {"comment": "ping"}
```

### Test Runtime Bootstrap
**Source:** `tests/conftest.py` lines 120-138 and 236-287
**Apply to:** `tests/test_room_lifecycle.py`, `tests/test_swipe_match.py`, `tests/test_repositories.py`
```python
def _bootstrap_temp_db_runtime(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)
    ...
    upgrade_to_head(sync_database_url)
    asyncio.run(initialize_runtime(runtime_database_url))


@pytest.fixture
def app(db_path, monkeypatch):
    ...
    fast_app.dependency_overrides[require_auth] = lambda: AuthUser(
        jf_token="valid-token", user_id="verified-user"
    )
```

## No Analog Found

None. Every planned file has at least a role-match or data-flow-match analog in the current codebase.

## Metadata

**Analog search scope:** `jellyswipe/`, `tests/`, `.planning/phases/38-auth-persistence-conversion/`
**Files scanned:** 17
**Pattern extraction date:** 2026-05-06
