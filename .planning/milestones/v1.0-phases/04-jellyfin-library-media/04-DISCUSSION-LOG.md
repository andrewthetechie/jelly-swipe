# Phase 4: Jellyfin library & media - Discussion Log

> **Audit trail only.** Decisions live in `04-CONTEXT.md`.

**Date:** 2026-04-22  
**Phase:** 4 — Jellyfin library & media  
**Mode:** `/gsd-discuss-phase 4 --chain`  
**Areas discussed:** Card id & JSON mapping · Genres/deck parity · `/proxy` allowlist · TMDB resolve · Server info · Resilience

---

## Defaults batch (`[chain] defaults`)

| Topic | Recommended | Selected |
|-------|-------------|----------|
| Card `id` | Jellyfin item GUID string end-to-end | ✓ |
| Thumb URLs | `/proxy?path=jellyfin/{guid}/Primary` with strict allowlist | ✓ |
| Movies library | First `CollectionType=movies` view from `/Users/Me` + Views | ✓ |
| Genres source | `/Items/Filters` with `/Genres` fallback; Sci-Fi label like Plex | ✓ |
| Deck rules | Match Plex: All/random, genre filter, Recently Added date sort no shuffle | ✓ |
| `/proxy` jellyfin | Same route; 503/403 matrix; provider fetches Primary image | ✓ |
| TMDB | `GET /Items/{id}` → `.title` / `.year` for existing routes | ✓ |
| Server info | `{machineIdentifier,name}` via System/Info or Public fallback | ✓ |
| Route rename | Keep `/plex/server-info` for both providers in this phase | ✓ |

**User's choice:** `[chain] defaults` (project convention from Phases 2–3).

---

## Claude's Discretion

- Jellyfin query params, image sizing query params, exact filter JSON shapes.

## Deferred Ideas

- See `04-CONTEXT.md` `<deferred>`.
