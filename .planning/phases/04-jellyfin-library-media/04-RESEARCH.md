# Phase 4 — Research notes (concise)

**Date:** 2026-04-24  
**Scope:** Jellyfin library/media parity surfaces (`/movies`, `/genres`, `/proxy`, TMDB resolve, server info).

## Findings (implementation-aligned)

1. **Card shape parity is already in provider code** — `_item_to_card()` emits `id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`, matching existing Plex-driven UI assumptions.
2. **Genre/deck behavior matches roadmap intent** — `list_genres()` uses `/Items/Filters` with `/Genres` fallback and normalizes `Science Fiction` → `Sci-Fi`; `fetch_deck()` honors `Recently Added` as date-desc/no-shuffle and randomized behavior for other modes.
3. **Image proxy safety remains strict** — both provider and route enforce a fixed `jellyfin/{id}/Primary` shape; current runtime accepts both canonical UUID and 32-hex item ids to avoid false 403s on valid Jellyfin servers while still preventing arbitrary proxy paths.
4. **TMDB + server-info parity path exists** — `resolve_item_for_tmdb()` uses authenticated `GET /Items/{id}` for title/year and `server_info()` maps Jellyfin system metadata to `{machineIdentifier, name}` for `/plex/server-info` compatibility.

## References (consult during execution)

- `.planning/phases/04-jellyfin-library-media/04-CONTEXT.md`
- `.planning/phases/03-jellyfin-authentication-http-client/03-CONTEXT.md`
- `.planning/REQUIREMENTS.md` (JLIB-01..05)
- `media_provider/jellyfin_library.py`
- `app.py`
