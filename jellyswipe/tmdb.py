"""Pure TMDB module — search, trailer, and cast lookups.

All failures (network, not found, bad response) return None or [].
The sync lookup functions use make_http_request for their HTTP calls;
TmdbClient owns an httpx.AsyncClient (mirroring
jellyswipe.jellyfin.client.JellyfinClient) so tests can inject a transport.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from jellyswipe.http_client import DEFAULT_USER_AGENT, make_http_request

_logger = logging.getLogger(__name__)

TMDB_SEARCH_TIMEOUT = (5, 15)
TMDB_BASE = "https://api.themoviedb.org/3"


def _first_search_result_id(payload: dict) -> int | None:
    """Return the id of the first movie search result, or None when absent."""
    results = payload.get("results")
    if not results:
        return None
    return results[0]["id"]


def _pick_trailer_key(videos_payload: dict) -> str | None:
    """Return the first YouTube trailer key from a TMDB videos payload."""
    trailers = [
        v
        for v in videos_payload.get("results", [])
        if v.get("site") == "YouTube" and v.get("type") == "Trailer"
    ]
    if trailers:
        return trailers[0]["key"]
    return None


def _map_cast(credits_payload: dict) -> list[dict]:
    """Map a TMDB credits payload to at most 8 cast-member dicts."""
    cast = []
    for actor in credits_payload.get("cast", [])[:8]:
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


def lookup_trailer(title: str, year: Optional[int], *, api_token: str) -> Optional[str]:
    """Search TMDB for a movie and return the YouTube trailer key.

    Returns None on any failure (network error, no match, no trailer).
    """
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        params = urlencode({"query": title, "year": year})
        search_url = f"{TMDB_BASE}/search/movie?{params}"
        search_response = make_http_request(
            method="GET",
            url=search_url,
            headers=headers,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        r = search_response.json()
        tmdb_id = _first_search_result_id(r)
        if tmdb_id is None:
            return None

        v_url = f"{TMDB_BASE}/movie/{tmdb_id}/videos"
        videos_response = make_http_request(
            method="GET",
            url=v_url,
            headers=headers,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        v_res = videos_response.json()
        return _pick_trailer_key(v_res)
    except Exception as e:
        _logger.warning(
            "TMDB trailer lookup failed",
            extra={"title": title, "year": year, "error": str(e)},
        )
        return None


def lookup_cast(title: str, year: Optional[int], *, api_token: str) -> list[dict]:
    """Search TMDB for a movie and return up to 8 cast members.

    Returns [] on any failure (network error, no match).
    """
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        params = urlencode({"query": title, "year": year})
        search_url = f"{TMDB_BASE}/search/movie?{params}"
        search_response = make_http_request(
            method="GET",
            url=search_url,
            headers=headers,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        r = search_response.json()
        tmdb_id = _first_search_result_id(r)
        if tmdb_id is None:
            return []

        credits_url = f"{TMDB_BASE}/movie/{tmdb_id}/credits"
        credits_response = make_http_request(
            method="GET",
            url=credits_url,
            headers=headers,
            timeout=TMDB_SEARCH_TIMEOUT,
        )
        c_res = credits_response.json()
        return _map_cast(c_res)
    except Exception as e:
        _logger.warning(
            "TMDB cast lookup failed",
            extra={"title": title, "year": year, "error": str(e)},
        )
        return []


class TmdbClient:
    """Async TMDB lookup client with an injectable transport.

    Holds the bearer token at construction and owns a single shared
    ``httpx.AsyncClient`` whose connect/read bounds are derived from
    ``TMDB_SEARCH_TIMEOUT`` (today ``(5, 15)`` seconds) and which sends the
    same ``User-Agent`` as the sync lookups. Mirrors
    :class:`jellyswipe.jellyfin.client.JellyfinClient`'s transport seam so tests
    can drive it with ``httpx.MockTransport``.

    All failures (network, not found, malformed response) are logged and
    returned as ``None`` / ``[]``, never raised; there are no retries.
    """

    def __init__(
        self,
        api_token: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_token = api_token
        connect_timeout, read_timeout = TMDB_SEARCH_TIMEOUT
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
            transport=transport,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._http.aclose()

    async def lookup_trailer(self, title: str, year: int | None) -> str | None:
        """Search TMDB for a movie and return the YouTube trailer key.

        Returns None on any failure (network error, no match, no trailer).
        """
        headers = {"Authorization": f"Bearer {self._api_token}"}
        try:
            params = urlencode({"query": title, "year": year})
            search_url = f"{TMDB_BASE}/search/movie?{params}"
            search_response = await self._http.get(search_url, headers=headers)
            search_response.raise_for_status()
            r = search_response.json()
            tmdb_id = _first_search_result_id(r)
            if tmdb_id is None:
                return None

            v_url = f"{TMDB_BASE}/movie/{tmdb_id}/videos"
            videos_response = await self._http.get(v_url, headers=headers)
            videos_response.raise_for_status()
            v_res = videos_response.json()
            return _pick_trailer_key(v_res)
        except Exception as e:
            _logger.warning(
                "TMDB trailer lookup failed",
                extra={"title": title, "year": year, "error": str(e)},
            )
            return None

    async def lookup_cast(self, title: str, year: int | None) -> list[dict]:
        """Search TMDB for a movie and return up to 8 cast members.

        Returns [] on any failure (network error, no match).
        """
        headers = {"Authorization": f"Bearer {self._api_token}"}
        try:
            params = urlencode({"query": title, "year": year})
            search_url = f"{TMDB_BASE}/search/movie?{params}"
            search_response = await self._http.get(search_url, headers=headers)
            search_response.raise_for_status()
            r = search_response.json()
            tmdb_id = _first_search_result_id(r)
            if tmdb_id is None:
                return []

            credits_url = f"{TMDB_BASE}/movie/{tmdb_id}/credits"
            credits_response = await self._http.get(credits_url, headers=headers)
            credits_response.raise_for_status()
            c_res = credits_response.json()
            return _map_cast(c_res)
        except Exception as e:
            _logger.warning(
                "TMDB cast lookup failed",
                extra={"title": title, "year": year, "error": str(e)},
            )
            return []
