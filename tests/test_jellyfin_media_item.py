"""Tests for ``jellyswipe.jellyfin_media_item`` pure functions.

All tests call the public functions directly with plain dicts.  No HTTP
mocking, no provider instantiation, and no custom fixtures beyond what
``pytest`` provides natively.
"""

import pytest
from jellyswipe.jellyfin_media_item import (
    GENRE_ALIASES,
    display_genre_name,
    movie_to_media_item,
    query_genre_name,
    series_to_media_item,
)


# ---------------------------------------------------------------------------
# movie_to_media_item
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_movie_to_media_item_full():
    """Fully-populated movie dict exercises every output field."""
    it = {
        "Id": "movie-123",
        "Name": "Test Movie",
        "Overview": "Test summary",
        "RunTimeTicks": 81000000000,
        "CommunityRating": 9.0,
        "CriticRating": 8.5,
        "ProductionYear": 2024,
    }
    result = movie_to_media_item(it)

    assert result["id"] == "movie-123"
    assert result["title"] == "Test Movie"
    assert result["summary"] == "Test summary"
    assert result["thumb"] == "/proxy?path=jellyfin/movie-123/Primary"
    assert result["rating"] == 9.0
    assert result["duration"] == "2h 15m"
    assert result["year"] == 2024
    assert result["media_type"] == "movie"


@pytest.mark.anyio
async def test_movie_to_media_item_missing_rating():
    """No CommunityRating or CriticRating yields rating None."""
    it = {
        "Id": "m2",
        "Name": "No Rating",
        "Overview": "",
        "RunTimeTicks": 0,
        "ProductionYear": 2022,
    }
    result = movie_to_media_item(it)
    assert result["rating"] is None


@pytest.mark.anyio
async def test_movie_to_media_item_critic_rating_fallback():
    """CriticRating is used when CommunityRating is absent."""
    it = {
        "Id": "m3",
        "Name": "Critic Only",
        "Overview": "",
        "RunTimeTicks": 27000000000,
        "ProductionYear": 2023,
        "CriticRating": 7.5,
    }
    result = movie_to_media_item(it)
    assert result["rating"] == 7.5
    assert result["duration"] == "45m"


@pytest.mark.anyio
async def test_movie_to_media_item_zero_runtime():
    """RunTimeTicks of zero produces an empty duration string."""
    it = {
        "Id": "m4",
        "Name": "No Runtime",
        "Overview": "",
        "RunTimeTicks": 0,
        "ProductionYear": 2021,
    }
    result = movie_to_media_item(it)
    assert result["duration"] == ""


@pytest.mark.anyio
async def test_movie_to_media_item_missing_year():
    """Missing ProductionYear yields None for year."""
    it = {
        "Id": "m5",
        "Name": "No Year",
        "Overview": "",
    }
    result = movie_to_media_item(it)
    assert result["year"] is None


# ---------------------------------------------------------------------------
# series_to_media_item
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_series_to_media_item_full():
    """Fully-populated series dict exercises every output field."""
    it = {
        "Id": "series-123",
        "Name": "Test Series",
        "Overview": "Test series summary",
        "ProductionYear": 2024,
        "ChildCount": 3,
        "Type": "Series",
    }
    result = series_to_media_item(it)

    assert result["id"] == "series-123"
    assert result["title"] == "Test Series"
    assert result["summary"] == "Test series summary"
    assert result["thumb"] == "/proxy?path=jellyfin/series-123/Primary"
    assert result["year"] == 2024
    assert result["media_type"] == "tv_show"
    assert result["season_count"] == 3
    assert "duration" not in result
    assert "rating" not in result


@pytest.mark.anyio
async def test_series_to_media_item_missing_child_count():
    """Missing ChildCount yields None for season_count, not an error."""
    it = {
        "Id": "series-456",
        "Name": "Series 2",
        "Overview": "",
        "ProductionYear": 2023,
    }
    result = series_to_media_item(it)
    assert result["season_count"] is None


# ---------------------------------------------------------------------------
# display_genre_name
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_display_genre_name_with_alias():
    """Known canonical genre returns its display alias."""
    assert display_genre_name("Science Fiction") == "Sci-Fi"


@pytest.mark.anyio
async def test_display_genre_name_no_alias():
    """Unknown genre is returned unchanged."""
    assert display_genre_name("Action") == "Action"


# ---------------------------------------------------------------------------
# query_genre_name
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_query_genre_name_with_alias():
    """Display alias is reverse-looked-up to canonical name."""
    assert query_genre_name("Sci-Fi") == "Science Fiction"


@pytest.mark.anyio
async def test_query_genre_name_no_alias():
    """Unknown display name is returned unchanged."""
    assert query_genre_name("Action") == "Action"


# ---------------------------------------------------------------------------
# GENRE_ALIASES round-trip
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_genre_alias_round_trip():
    """Every alias pair round-trips correctly in both directions."""
    for canonical, display in GENRE_ALIASES.items():
        assert query_genre_name(display_genre_name(canonical)) == canonical
        assert display_genre_name(query_genre_name(display)) == display
