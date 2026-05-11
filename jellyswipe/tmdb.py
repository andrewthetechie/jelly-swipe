"""Pure TMDB lookup module — zero external dependencies.

All functions are best-effort enrichment. Network failures, missing results,
and malformed responses return safe defaults (None or []).
"""

from urllib.parse import urlencode

from jellyswipe.config import TMDB_AUTH_HEADERS
from jellyswipe.http_client import make_http_request

TMDB_BASE_URL = "https://api.themoviedb.org/3"


def lookup_trailer(title: str, year) -> str | None:
    """Search TMDB for a movie, return YouTube trailer key.

    Steps:
    1. GET /search/movie?query={title}&year={year}
    2. Take first result's tmdb_id
    3. GET /movie/{tmdb_id}/videos
    4. Find first YouTube Trailer

    All failures return None. Best-effort enrichment.
    """
    try:
        params = urlencode({"query": title, "year": year})
        search_url = f"{TMDB_BASE_URL}/search/movie?{params}"
        search_response = make_http_request(
            method="GET", url=search_url, headers=TMDB_AUTH_HEADERS, timeout=(5, 15)
        )
        r = search_response.json()
        if not r.get("results"):
            return None
        tmdb_id = r["results"][0]["id"]

        v_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/videos"
        videos_response = make_http_request(
            method="GET", url=v_url, headers=TMDB_AUTH_HEADERS, timeout=(5, 15)
        )
        v_res = videos_response.json()
        trailers = [
            v
            for v in v_res.get("results", [])
            if v["site"] == "YouTube" and v["type"] == "Trailer"
        ]
        return trailers[0]["key"] if trailers else None
    except Exception:
        return None


def lookup_cast(title: str, year) -> list[dict]:
    """Search TMDB for a movie, return up to 8 cast members.

    Returns list of {"name": str, "character": str, "profile_path": str | None}.
    All failures return [].
    """
    try:
        params = urlencode({"query": title, "year": year})
        search_url = f"{TMDB_BASE_URL}/search/movie?{params}"
        search_response = make_http_request(
            method="GET", url=search_url, headers=TMDB_AUTH_HEADERS, timeout=(5, 15)
        )
        r = search_response.json()
        if not r.get("results"):
            return []
        tmdb_id = r["results"][0]["id"]

        credits_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits"
        credits_response = make_http_request(
            method="GET", url=credits_url, headers=TMDB_AUTH_HEADERS, timeout=(5, 15)
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
