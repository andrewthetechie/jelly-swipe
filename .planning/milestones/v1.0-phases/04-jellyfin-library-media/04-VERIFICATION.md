---
phase: 4
status: complete
verified: 2026-04-24
---

# Phase 4 verification (JLIB-01 — JLIB-05) + Jellyfin ARC-02 slice

Route-level and code evidence under **`MEDIA_PROVIDER=jellyfin`**. Full deck/thumb success requires a **healthy Jellyfin** upstream; this closure records **local Flask** behavior with **unreachable** `JELLYFIN_URL` (connection refused), matching the spirit of `02-VERIFICATION.md` Plex rows.

**Cross-reference (Plex baseline):** [`02-VERIFICATION.md`](../02-media-provider-abstraction/02-VERIFICATION.md)

## Traceability

| Requirement | Status | Evidence summary | Date |
|-------------|--------|------------------|------|
| JLIB-01 | PARTIAL | `fetch_deck` maps Jellyfin item fields to UI card keys in `jellyfin_library.py`; live deck JSON not captured without upstream. | 2026-04-24 |
| JLIB-02 | PARTIAL | `list_genres` / `fetch_deck` ordering logic in code; `GET /genres` returns `[]` when provider errors are swallowed by route. | 2026-04-24 |
| JLIB-03 | PASS | `/proxy` allowlist regex rejects non-`jellyfin/{id}/Primary` paths with **403** before image fetch; allowlisted path hits provider and returns **500** when upstream refuses connection (observed). | 2026-04-24 |
| JLIB-04 | PARTIAL | Routes delegate to `resolve_item_for_tmdb`; upstream item fetch fails without server — error path returns JSON without leaking tokens (spot-checked). | 2026-04-24 |
| JLIB-05 | PARTIAL | `GET /plex/server-info` returns **500** JSON error on connection refused after auth probe — confirms route + JSON wrapper; not `{machineIdentifier,name}` without server. | 2026-04-24 |

## ARC-02 — Route checklist (Jellyfin mode, local app)

Environment: `env -i PATH HOME MEDIA_PROVIDER=jellyfin JELLYFIN_URL=http://127.0.0.1:8096` + dummy secrets for Flask/TMDB only, **no** Jellyfin on `8096`, Flask `test_client`.

| Check | HTTP path | Observed outcome | Status | Date |
|-------|-----------|------------------|--------|------|
| Server info JSON (error path) | `GET /plex/server-info` | HTTP **500**, JSON `error` with connection refused text | PARTIAL | 2026-04-24 |
| Genre list | `GET /genres` | HTTP **200**, body `[]` | PARTIAL | 2026-04-24 |
| Room + deck load | `POST /room/create` | Not re-run in this table (requires `get_provider().fetch_deck()` success) | PENDING | 2026-04-24 |
| Trailer chain | `GET /get-trailer/1` | Not re-run | PENDING | 2026-04-24 |
| Cast chain | `GET /cast/1` | Not re-run | PENDING | 2026-04-24 |
| Image proxy allowlist | `GET /proxy?path=jellyfin/00000000000000000000000000000000/Primary` | HTTP **500** (upstream after allowlist) | PARTIAL | 2026-04-24 |
| Image proxy reject | `GET /proxy?path=/library/metadata/x` | HTTP **403** | PASS | 2026-04-24 |

**Closure note:** Move JLIB/ARC rows to **PASS** by re-running this table against a reachable Jellyfin with a Movies library and known item ids (no tokens in this file).

## JLIB-01 — Card field mapping (code)

Deck construction uses Jellyfin `Id`, `Name`, `Overview`, `ProductionYear`, `CommunityRating`, `RunTimeTicks`, and `thumb` URLs via `/proxy?path=jellyfin/.../Primary` (see `JellyfinLibraryProvider` in `media_provider/jellyfin_library.py`).

## JLIB-03 — `/proxy` allowlist (live)

Observed with `test_client`: disallowed path → **403**; allowlisted synthetic id → **500** after provider attempts upstream fetch (stack confirms `/Items` probe / image path).
