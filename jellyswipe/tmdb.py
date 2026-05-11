"""Pure TMDB module — search, trailer, and cast lookups.

All failures (network, not found, bad response) return None or [].
Uses make_http_request for actual HTTP calls.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode

from jellyswipe.config import TMDB_AUTH_HEADERS
from jellyswipe.http_client import make_http_request

_logger = logging.getLogger(__name__)

TMDB_SEARCH_TIMEOUT = (5, 15)
TMDB_BASE = "https://api.themoviedb.org/3"


def lookup_trailer(title: str, year: Optional[int]) -> Optional[str]:
    """Search TMDB for a movie and return the YouTube trailer key.

    Returns None on any failure (network error, no match, no trailer).
    """
    try:
        params = urlencode({"query": title, "year": year})
        search_url = f"{TMDB_BASE}/search/movie?{params}"
        search_response = make_http_request(
            method="GET",
            url=search_url,
            headers=TMDB_AUTH_HEADERS,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        r = search_response.json()
        if not r.get("results"):
            return None

        tmdb_id = r["results"][0]["id"]
        v_url = f"{TMDB_BASE}/movie/{tmdb_id}/videos"
        videos_response = make_http_request(
            method="GET",
            url=v_url,
            headers=TMDB_AUTH_HEADERS,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        v_res = videos_response.json()
        trailers = [
            v
            for v in v_res.get("results", [])
            if v.get("site") == "YouTube" and v.get("type") == "Trailer"
        ]
        if trailers:
            return trailers[0]["key"]
        return None
    except Exception:
        return None


def lookup_cast(title: str, year: Optional[int]) -> list[dict]:
    """Search TMDB for a movie and return up to 8 cast members.

    Returns [] on any failure (network error, no match).
    """
    try:
        params = urlencode({"query": title, "year": year})
        search_url = f"{TMDB_BASE}/search/movie?{params}"
        search_response = make_http_request(
            method="GET",
            url=search_url,
            headers=TMDB_AUTH_HEADERS,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        r = search_response.json()
        if not r.get("results"):
            return []

        tmdb_id = r["results"][0]["id"]
        credits_url = f"{TMDB_BASE}/movie/{tmdb_id}/credits"
        credits_response = make_http_request(
            method="GET",
            url=credits_url,
            headers=TMDB_AUTH_HEADERS,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        c_res = credits_response.json()
        cast = []
        for actor in c_res.get("cast", [])[:8]:
            cast.append(
                {
                    "name": actor["name"],
                    "character": actor.get("character", ""),
                    "profile_path": f"https://image.tmdb.org/t/p/w185{actor['profile_path']}"
                    if actor.get("profile_path")
                    else None,
                }
            )
        return cast
    except Exception:
        return []
