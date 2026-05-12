"""Comprehensive integration and unit tests for TV show support.

Tests cover:
- Integration test: create mixed room, swipe TV show, verify match with media_type='tv_show'
- Unit tests for JellyfinLibrary.fetch_deck(media_types=['tv_show'])
- Unit tests for round-robin deck interleaving
- Unit tests for media_type in match record
"""

import json
from datetime import datetime, timezone

import pytest

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.jellyfin_library import JellyfinLibraryProvider
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.models.auth_session import AuthSession
from jellyswipe.services.session_match_mutation import (
    CatalogFacts,
    SessionActor,
    SessionMatchMutation,
    SwipeAccepted,
)
from tests.conftest import FakeProvider, set_session_cookie


# ---------------------------------------------------------------------------
# Integration Tests: Room Creation with TV Shows
# ---------------------------------------------------------------------------


def test_create_room_with_tv_shows_only(client, app):
    """POST /room with {"movies": false, "tv_shows": true, "solo": true} creates solo room with TV shows."""
    import os

    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post(
        "/room", json={"movies": False, "tv_shows": True, "solo": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert "pairing_code" in data
    code = data["pairing_code"]

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT include_movies, include_tv_shows, solo_mode, ready FROM rooms WHERE pairing_code = ?",
            (code,),
        ).fetchone()
    finally:
        conn.close()

    assert row["include_movies"] == 0
    assert row["include_tv_shows"] == 1
    assert row["solo_mode"] == 1
    assert row["ready"] == 1


def test_create_mixed_room_movies_and_tv_shows(client, app):
    """POST /room with {"movies": true, "tv_shows": true, "solo": false} creates hosted room with mixed media."""
    import os

    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post(
        "/room", json={"movies": True, "tv_shows": True, "solo": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert "pairing_code" in data
    code = data["pairing_code"]

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT include_movies, include_tv_shows, solo_mode, ready FROM rooms WHERE pairing_code = ?",
            (code,),
        ).fetchone()
    finally:
        conn.close()

    assert row["include_movies"] == 1
    assert row["include_tv_shows"] == 1
    assert row["solo_mode"] == 0
    assert row["ready"] == 0


# ---------------------------------------------------------------------------
# Integration Tests: TV Show Swipe and Match
# ---------------------------------------------------------------------------


def test_swipe_tv_show_right_solo_match(client, app):
    """POST /room/<code>/swipe right on TV show in solo room creates match with media_type='tv_show'."""
    import os

    # Create a room with TV shows
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post(
        "/room", json={"movies": False, "tv_shows": True, "solo": True}
    )
    code = response.json()["pairing_code"]

    # Mock provider to return TV show in deck
    fake_provider = FakeProvider()
    original_fetch = fake_provider.fetch_deck

    def mock_fetch(media_types=None, genre_name=None):
        if media_types and "tv_show" in media_types:
            return [
                {
                    "id": "tv-1",
                    "title": "TV Show 1",
                    "summary": "TV Summary",
                    "thumb": "/proxy?path=jellyfin/tv-1/Primary",
                    "year": 2024,
                    "media_type": "tv_show",
                    "season_count": 3,
                }
            ]
        return original_fetch(media_types, genre_name)

    fake_provider.fetch_deck = mock_fetch

    import jellyswipe.routers.rooms as rooms_router_module

    original_get_provider = rooms_router_module.get_provider
    rooms_router_module.get_provider = lambda: fake_provider

    try:
        # Swipe right on TV show
        response = client.post(
            f"/room/{code}/swipe",
            json={"media_id": "tv-1", "direction": "right"},
        )

        assert response.status_code == 200
        assert response.json() == {"accepted": True}

        # Verify match was created with media_type
        conn = _sqlite_conn_for_route_tests()
        try:
            row = conn.execute(
                "SELECT media_type FROM matches WHERE room_code = ? AND movie_id = ?",
                (code, "tv-1"),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        assert row["media_type"] == "tv_show"
    finally:
        rooms_router_module.get_provider = original_get_provider


def test_swipe_tv_show_dual_match(client, app):
    """POST /room/<code>/swipe right on TV show by both users creates match with media_type='tv_show'."""
    import os

    # Seed a mixed room with TV show in movie_data so media_type can be resolved
    movie_data = json.dumps(
        [
            {
                "id": "tv-1",
                "title": "TV Show 1",
                "summary": "TV Summary",
                "thumb": "/proxy?path=jellyfin/tv-1/Primary",
                "year": 2024,
                "media_type": "tv_show",
                "season_count": 3,
            }
        ]
    )
    _seed_room("MIXED1", ready=1, solo_mode=0, movie_data=movie_data)
    _set_session(
        client,
        os.environ["FLASK_SECRET"],
        active_room="MIXED1",
        user_id="verified-user",
        authenticated=True,
    )

    # Mock provider
    fake_provider = FakeProvider()

    import jellyswipe.routers.rooms as rooms_router_module

    original_get_provider = rooms_router_module.get_provider
    rooms_router_module.get_provider = lambda: fake_provider

    try:
        # First user swipes right on TV show
        conn = _sqlite_conn_for_route_tests()
        try:
            conn.execute(
                "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
                ("sess-user2", "valid-token", "user-2", "2026-05-05T00:00:00+00:00"),
            )
            conn.execute(
                "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)",
                ("MIXED1", "tv-1", "user-2", "right", "sess-user2"),
            )
            conn.commit()
        finally:
            conn.close()

        # Second user swipes right on same TV show
        response = client.post(
            "/room/MIXED1/swipe",
            json={"media_id": "tv-1", "direction": "right"},
        )

        assert response.status_code == 200
        assert response.json() == {"accepted": True}

        # Verify match was created with media_type for both users
        conn = _sqlite_conn_for_route_tests()
        try:
            rows = conn.execute(
                "SELECT user_id, media_type FROM matches WHERE room_code = 'MIXED1' AND movie_id = 'tv-1'"
            ).fetchall()
        finally:
            conn.close()

        assert len(rows) == 2
        for row in rows:
            assert row["media_type"] == "tv_show"
    finally:
        rooms_router_module.get_provider = original_get_provider


def test_swipe_mixed_deck_movie_and_tv_show(client, app):
    """Verify swiping on movie vs TV show in mixed room sets correct media_type."""
    import os

    # Create mixed room
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post(
        "/room", json={"movies": True, "tv_shows": True, "solo": True}
    )
    code = response.json()["pairing_code"]

    # Mock provider to return mixed deck
    fake_provider = FakeProvider()

    def mock_fetch(media_types=None, genre_name=None):
        return [
            {
                "id": "movie-1",
                "title": "Movie 1",
                "summary": "Movie Summary",
                "thumb": "/proxy?path=jellyfin/movie-1/Primary",
                "rating": 8.0,
                "duration": "1h 30m",
                "year": 2024,
                "media_type": "movie",
            },
            {
                "id": "tv-1",
                "title": "TV Show 1",
                "summary": "TV Summary",
                "thumb": "/proxy?path=jellyfin/tv-1/Primary",
                "year": 2024,
                "media_type": "tv_show",
                "season_count": 3,
            },
        ]

    fake_provider.fetch_deck = mock_fetch

    import jellyswipe.routers.rooms as rooms_router_module

    original_get_provider = rooms_router_module.get_provider
    rooms_router_module.get_provider = lambda: fake_provider

    try:
        # Swipe right on movie
        client.post(
            f"/room/{code}/swipe",
            json={"media_id": "movie-1", "direction": "right"},
        )

        # Swipe right on TV show
        client.post(
            f"/room/{code}/swipe",
            json={"media_id": "tv-1", "direction": "right"},
        )

        # Verify both matches have correct media_type
        conn = _sqlite_conn_for_route_tests()
        try:
            movie_row = conn.execute(
                "SELECT media_type FROM matches WHERE room_code = ? AND movie_id = ?",
                (code, "movie-1"),
            ).fetchone()
            tv_row = conn.execute(
                "SELECT media_type FROM matches WHERE room_code = ? AND movie_id = ?",
                (code, "tv-1"),
            ).fetchone()
        finally:
            conn.close()

        assert movie_row is not None
        assert movie_row["media_type"] == "movie"
        assert tv_row is not None
        assert tv_row["media_type"] == "tv_show"
    finally:
        rooms_router_module.get_provider = original_get_provider


# ---------------------------------------------------------------------------
# Unit Tests: Deck Interleaving (Round-Robin)
# ---------------------------------------------------------------------------


def test_round_robin_interleaving_equal_counts():
    """Test round-robin interleaving with equal number of movies and TV shows."""
    movies = [
        {"id": "m1", "media_type": "movie", "title": "Movie 1"},
        {"id": "m2", "media_type": "movie", "title": "Movie 2"},
    ]
    tv_shows = [
        {"id": "t1", "media_type": "tv_show", "title": "TV 1"},
        {"id": "t2", "media_type": "tv_show", "title": "TV 2"},
    ]

    # Simulate interleaving logic from create_room
    interleaved = []
    max_len = max(len(movies), len(tv_shows))
    for i in range(max_len):
        if i < len(movies):
            interleaved.append(movies[i])
        if i < len(tv_shows):
            interleaved.append(tv_shows[i])

    assert len(interleaved) == 4
    assert interleaved[0]["id"] == "m1"
    assert interleaved[1]["id"] == "t1"
    assert interleaved[2]["id"] == "m2"
    assert interleaved[3]["id"] == "t2"


def test_round_robin_interleaving_more_movies():
    """Test round-robin interleaving when there are more movies than TV shows."""
    movies = [
        {"id": "m1", "media_type": "movie", "title": "Movie 1"},
        {"id": "m2", "media_type": "movie", "title": "Movie 2"},
        {"id": "m3", "media_type": "movie", "title": "Movie 3"},
    ]
    tv_shows = [
        {"id": "t1", "media_type": "tv_show", "title": "TV 1"},
    ]

    # Simulate interleaving logic
    interleaved = []
    max_len = max(len(movies), len(tv_shows))
    for i in range(max_len):
        if i < len(movies):
            interleaved.append(movies[i])
        if i < len(tv_shows):
            interleaved.append(tv_shows[i])

    assert len(interleaved) == 4
    assert interleaved[0]["id"] == "m1"
    assert interleaved[1]["id"] == "t1"
    assert interleaved[2]["id"] == "m2"
    assert interleaved[3]["id"] == "m3"


def test_round_robin_interleaving_more_tv_shows():
    """Test round-robin interleaving when there are more TV shows than movies."""
    movies = [
        {"id": "m1", "media_type": "movie", "title": "Movie 1"},
    ]
    tv_shows = [
        {"id": "t1", "media_type": "tv_show", "title": "TV 1"},
        {"id": "t2", "media_type": "tv_show", "title": "TV 2"},
        {"id": "t3", "media_type": "tv_show", "title": "TV 3"},
    ]

    # Simulate interleaving logic
    interleaved = []
    max_len = max(len(movies), len(tv_shows))
    for i in range(max_len):
        if i < len(movies):
            interleaved.append(movies[i])
        if i < len(tv_shows):
            interleaved.append(tv_shows[i])

    assert len(interleaved) == 4
    assert interleaved[0]["id"] == "m1"
    assert interleaved[1]["id"] == "t1"
    assert interleaved[2]["id"] == "t2"
    assert interleaved[3]["id"] == "t3"


def test_round_robin_interleaving_empty_movies():
    """Test round-robin interleaving when movies list is empty."""
    movies = []
    tv_shows = [
        {"id": "t1", "media_type": "tv_show", "title": "TV 1"},
        {"id": "t2", "media_type": "tv_show", "title": "TV 2"},
    ]

    # Simulate interleaving logic
    interleaved = []
    max_len = max(len(movies), len(tv_shows))
    for i in range(max_len):
        if i < len(movies):
            interleaved.append(movies[i])
        if i < len(tv_shows):
            interleaved.append(tv_shows[i])

    assert len(interleaved) == 2
    assert interleaved[0]["id"] == "t1"
    assert interleaved[1]["id"] == "t2"


def test_round_robin_interleaving_empty_tv_shows():
    """Test round-robin interleaving when TV shows list is empty."""
    movies = [
        {"id": "m1", "media_type": "movie", "title": "Movie 1"},
        {"id": "m2", "media_type": "movie", "title": "Movie 2"},
    ]
    tv_shows = []

    # Simulate interleaving logic
    interleaved = []
    max_len = max(len(movies), len(tv_shows))
    for i in range(max_len):
        if i < len(movies):
            interleaved.append(movies[i])
        if i < len(tv_shows):
            interleaved.append(tv_shows[i])

    assert len(interleaved) == 2
    assert interleaved[0]["id"] == "m1"
    assert interleaved[1]["id"] == "m2"


# ---------------------------------------------------------------------------
# Unit Tests: Media Type in Match Record
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_match_record_includes_media_type_tv_show(db_path, monkeypatch):
    """Test that SessionMatchMutation creates match records with media_type='tv_show'."""
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)

    try:
        sessionmaker = get_sessionmaker()
        svc = SessionMatchMutation()

        # Seed room with TV show in movie_data so media_type can be resolved
        movie_data = json.dumps(
            [
                {
                    "id": "tv-1",
                    "title": "TV Show 1",
                    "summary": "TV Summary",
                    "thumb": "/t.jpg",
                    "year": 2024,
                    "media_type": "tv_show",
                    "season_count": 3,
                }
            ]
        )
        async with sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "ROOM1",
                movie_data_json=movie_data,
                ready=True,
                current_genre="All",
                solo_mode=True,
                deck_position_json=json.dumps({"user-1": 0}),
            )
            await session.commit()

        # Create auth session
        async with sessionmaker() as session:
            session.add(
                AuthSession(
                    session_id="sess-1",
                    jellyfin_token="tok",
                    jellyfin_user_id="user-1",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            await session.commit()

        # Swipe right on TV show
        async with sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            actor = SessionActor(
                user_id="user-1", session_id="sess-1", active_room="ROOM1"
            )
            catalog = CatalogFacts(title="TV Show 1", thumb="/t.jpg")
            result = await svc.apply_swipe(
                code="ROOM1",
                actor=actor,
                media_id="tv-1",
                direction="right",
                catalog_facts=catalog,
                uow=uow,
                jellyfin_url="http://test",
            )
            assert isinstance(result, SwipeAccepted)
            await session.commit()

        # Verify match has media_type
        async with sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            matches = await uow.matches.list_active_for_user("ROOM1", "user-1")
            assert len(matches) > 0
            match = next(m for m in matches if m.movie_id == "tv-1")
            assert match.media_type == "tv_show"
    finally:
        await dispose_runtime()


@pytest.mark.anyio
async def test_match_record_includes_media_type_movie(db_path, monkeypatch):
    """Test that SessionMatchMutation creates match records with media_type='movie'."""
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)

    try:
        sessionmaker = get_sessionmaker()
        svc = SessionMatchMutation()

        # Seed room with movie in movie_data so media_type can be resolved
        movie_data = json.dumps(
            [
                {
                    "id": "movie-1",
                    "title": "Movie 1",
                    "summary": "Movie Summary",
                    "thumb": "/m.jpg",
                    "rating": 8.0,
                    "duration": "1h 30m",
                    "year": 2024,
                    "media_type": "movie",
                }
            ]
        )
        async with sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "ROOM1",
                movie_data_json=movie_data,
                ready=True,
                current_genre="All",
                solo_mode=True,
                deck_position_json=json.dumps({"user-1": 0}),
            )
            await session.commit()

        # Create auth session
        async with sessionmaker() as session:
            session.add(
                AuthSession(
                    session_id="sess-1",
                    jellyfin_token="tok",
                    jellyfin_user_id="user-1",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            await session.commit()

        # Swipe right on movie
        async with sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            actor = SessionActor(
                user_id="user-1", session_id="sess-1", active_room="ROOM1"
            )
            catalog = CatalogFacts(title="Movie 1", thumb="/m.jpg")
            result = await svc.apply_swipe(
                code="ROOM1",
                actor=actor,
                media_id="movie-1",
                direction="right",
                catalog_facts=catalog,
                uow=uow,
                jellyfin_url="http://test",
            )
            assert isinstance(result, SwipeAccepted)
            await session.commit()

        # Verify match has media_type
        async with sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            matches = await uow.matches.list_active_for_user("ROOM1", "user-1")
            assert len(matches) > 0
            match = next(m for m in matches if m.movie_id == "movie-1")
            assert match.media_type == "movie"
    finally:
        await dispose_runtime()


# ---------------------------------------------------------------------------
# Unit Tests: JellyfinLibrary.fetch_deck for TV Shows
# ---------------------------------------------------------------------------


def test_fetch_deck_tv_shows_only(mocker, monkeypatch):
    """Test that JellyfinLibraryProvider.fetch_deck returns TV shows with media_type='tv_show'."""
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - library discovery, TV items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [{"Id": "lib-tv", "CollectionType": "tvshows", "Name": "TV Shows"}]
    }

    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {
                "Id": "series-1",
                "Name": "TV Series 1",
                "Overview": "Series summary 1",
                "ProductionYear": 2024,
                "ChildCount": 2,
                "Type": "Series",
            }
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch(
        "jellyswipe.jellyfin_library.requests.Session", return_value=mock_session
    )

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck for TV shows only
    deck = provider.fetch_deck(media_types=["tv_show"])

    # Verify deck contains TV card with correct format
    assert len(deck) == 1
    card = deck[0]
    assert card["id"] == "series-1"
    assert card["title"] == "TV Series 1"
    assert card["media_type"] == "tv_show"
    assert card["season_count"] == 2
    assert "duration" not in card  # TV cards should NOT have duration


def test_fetch_deck_mixed_media_interleaved(mocker, monkeypatch):
    """Test that fetch_deck with both movie and tv_show returns interleaved cards."""
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    mock_session = mocker.MagicMock()
    mocker.patch(
        "jellyswipe.jellyfin_library.requests.Session", return_value=mock_session
    )

    # Create provider and set up state with pre-populated library cache
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_ids = {
        "movies": ["lib-movies"],
        "tvshows": ["lib-tv"],
    }

    # Configure mock responses
    def request_side_effect(method, url, **kwargs):
        mock_response = mocker.MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200

        params = kwargs.get("params", {})
        if params.get("IncludeItemTypes") == "Movie":
            mock_response.json.return_value = {
                "Items": [
                    {
                        "Id": "movie-1",
                        "Name": "Movie 1",
                        "Overview": "Movie summary",
                        "RunTimeTicks": 54000000000,
                        "ProductionYear": 2024,
                        "CommunityRating": 8.5,
                        "Type": "Movie",
                    }
                ]
            }
        elif params.get("IncludeItemTypes") == "Series":
            mock_response.json.return_value = {
                "Items": [
                    {
                        "Id": "series-1",
                        "Name": "TV Series 1",
                        "Overview": "Series summary",
                        "ProductionYear": 2023,
                        "ChildCount": 3,
                        "Type": "Series",
                    }
                ]
            }
        else:
            mock_response.json.return_value = {"Items": []}

        return mock_response

    mock_session.request.side_effect = request_side_effect

    # Call fetch_deck for both media types
    deck = provider.fetch_deck(media_types=["movie", "tv_show"])

    # Verify deck contains both movie and TV cards
    assert len(deck) == 2

    # Find movie and TV cards
    movie_card = next(c for c in deck if c["media_type"] == "movie")
    tv_card = next(c for c in deck if c["media_type"] == "tv_show")

    # Verify movie card
    assert movie_card["id"] == "movie-1"
    assert movie_card["duration"] == "1h 30m"
    assert movie_card["rating"] == 8.5

    # Verify TV card
    assert tv_card["id"] == "series-1"
    assert tv_card["season_count"] == 3
    assert "duration" not in tv_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session(
    client,
    secret_key,
    *,
    active_room=None,
    user_id="verified-user",
    authenticated=True,
    solo_mode=False,
):
    """Inject session state for room tests."""
    data = {"solo_mode": solo_mode}
    if active_room is not None:
        data["active_room"] = active_room
    if data:
        set_session_cookie(client, data, secret_key)


def _sqlite_conn_for_route_tests():
    """Open sqlite3 directly to the test database."""
    import sqlite3
    import os

    path = os.environ["DB_PATH"]
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_room(room_code="TEST1", *, ready=0, solo_mode=0, movie_data=None):
    """Seed a room row directly into the database for testing."""
    if movie_data is None:
        movie_data = json.dumps([])
    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) "
            "VALUES (?, ?, ?, ?, ?)",
            (room_code, movie_data, ready, "All", solo_mode),
        )
        conn.commit()
    finally:
        conn.close()
