# Pitfalls Research

**Domain:** Jellyfin + Flask media proxy  
**Researched:** 2026-04-22

## Pitfall: Legacy auth headers disabled

**Warning signs:** 401 on all endpoints after server upgrade; admin enabled “disable legacy authorization”.  
**Prevention:** Implement `Authorization: MediaBrowser ...` with Token; verify on target Jellyfin version.  
**Phase:** Jellyfin client / auth phase.

## Pitfall: Image URL and path validation

**Warning signs:** `/proxy` returns 403 for valid Jellyfin thumbs; open redirect if path not validated.  
**Prevention:** Separate query param contract per provider (`path=` for Plex, `item_id=` + `image_type=` for Jellyfin, etc.); strict allowlists.  
**Phase:** Image proxy phase.

## Pitfall: ID collisions in SQLite `plex_id` column

**Warning signs:** Matches from two users merge incorrectly when both use string `"null"`.  
**Prevention:** Treat `plex_id` as opaque `user_scope_id`; in Jellyfin mode store Jellyfin user id from auth; document column rename as follow-up optional cleanup.  
**Phase:** User parity phase.

## Pitfall: Genre model mismatch

**Warning signs:** Empty genre list or missing movies when filtering.  
**Prevention:** Map Jellyfin `Genres` array to the same display strings the UI lists; fallback to “All” only.  
**Phase:** Library fetch phase.

## Pitfall: Startup imports require Plex env

**Warning signs:** Jellyfin-only `.env` still crashes on missing `PLEX_TOKEN`.  
**Prevention:** Lazy-import Plex or branch `required` env list before `PlexServer` construction.  
**Phase:** Configuration phase.

---
*Pitfalls research for Jellyfin milestone*
