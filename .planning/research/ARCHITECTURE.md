# Architecture Research

**Domain:** Adding Jellyfin alongside existing Plex integration  
**Researched:** 2026-04-22

## Component boundaries

| Component | Responsibility |
|-----------|----------------|
| **Config / bootstrap** | Read `MEDIA_PROVIDER` (or equivalent); validate required env vars for the active provider only; avoid importing Plex-only modules unnecessarily at startup. |
| **Media provider interface** | `genres()`, `movies(genre)`, `item(movie_id)`, `server_info()`, `image_response(path_or_descriptor)` — returns data shapes the rest of `app.py` (or templates) already expect. |
| **Plex implementation** | Current `get_plex`, `fetch_plex_movies`, `get_plex_genres`, Plex-backed `/proxy` behavior. |
| **Jellyfin implementation** | HTTP client with token; `/Users/AuthenticateByName` or API key flow; `/Items` queries for library + filters; image fetch for thumbs. |
| **Routes** | Thin: delegate to active provider; keep TMDB routes using abstract `item` metadata. |

## Data flow

1. **Room create** → provider fetches N movies → JSON stored in `rooms.movie_data` (unchanged schema intent).  
2. **Genre change** → provider refetch → same JSON shape.  
3. **Trailer/cast** → provider `item(id)` → TMDB search (unchanged).  
4. **Thumbs** → client hits app proxy with provider-specific query → server fetches from Jellyfin or Plex with credentials.

## Suggested build order

1. Config split and validation (fail fast).  
2. Extract Plex behind provider API (behavior unchanged).  
3. Implement Jellyfin provider: auth + list items + images.  
4. Wire user headers / watchlist parity for Jellyfin users.  
5. Docs (`README`, `docker-compose` example) and manual test matrix.

---
*Architecture research for Jellyfin milestone*
