"""Pure, side-effect-free media-item transformation utilities.

Extracted from ``JellyfinLibraryProvider`` so that the conversion logic
can be reused without importing the HTTP-aware provider class.
"""

from __future__ import annotations

GENRE_ALIASES: dict[str, str] = {
    "Science Fiction": "Sci-Fi",
}


def _format_runtime(seconds: int) -> str:
    """Format seconds as a human-readable duration string."""
    if seconds <= 0:
        return ""
    hrs, rem = divmod(seconds, 3600)
    mins = rem // 60
    if hrs > 0:
        return f"{hrs}h {mins}m"
    return f"{mins}m"


def movie_to_media_item(it: dict) -> dict:
    """Transform a raw Jellyfin Movie item dict into a card dict."""
    mid = it.get("Id")
    ticks = int(it.get("RunTimeTicks") or 0)
    seconds = ticks // 10_000_000 if ticks else 0
    rating = it.get("CommunityRating")
    if rating is None:
        rating = it.get("CriticRating")
    return {
        "id": mid,
        "title": it.get("Name") or "",
        "summary": it.get("Overview") or "",
        "thumb": f"/proxy?path=jellyfin/{mid}/Primary",
        "rating": rating,
        "duration": _format_runtime(seconds),
        "year": it.get("ProductionYear"),
        "media_type": "movie",
    }


def series_to_media_item(it: dict) -> dict:
    """Transform a raw Jellyfin Series item dict into a card dict."""
    mid = it.get("Id")
    return {
        "id": mid,
        "title": it.get("Name") or "",
        "summary": it.get("Overview") or "",
        "thumb": f"/proxy?path=jellyfin/{mid}/Primary",
        "year": it.get("ProductionYear"),
        "media_type": "tv_show",
        "season_count": it.get("ChildCount"),
    }


def display_genre_name(name: str) -> str:
    """Return a display-friendly genre name (e.g. "Sci-Fi")."""
    return GENRE_ALIASES.get(name, name)


def query_genre_name(name: str) -> str:
    """Reverse-lookup a display name to the canonical Jellyfin genre name.

    If *name* is not found in the reverse mapping it is returned unchanged.
    """
    reverse = {v: k for k, v in GENRE_ALIASES.items()}
    return reverse.get(name, name)
