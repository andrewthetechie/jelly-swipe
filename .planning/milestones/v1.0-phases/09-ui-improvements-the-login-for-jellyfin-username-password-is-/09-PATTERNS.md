# Phase 9 — Pattern map

Analogs and excerpts for Phase 9 execution.

## Flask auth routes

| New work | Analog | Notes |
|----------|--------|-------|
| Extend `/auth/provider` | `app.py` lines 226–228 | Return JSON only; add fields alongside `provider`. |
| Session-backed identity | `session['active_room']` usage in `create_room` | Same signed-session mechanism. |

## Jellyfin provider

| New work | Analog | Excerpt |
|----------|--------|---------|
| Expose server token safely | `_auth_headers` uses `_access_token` | `ensure_authenticated()` must precede any read. |
| User id for env login | `_user_id()` in `jellyfin_library.py` | Resolves admin/API-key users via `/Users` when `/Users/Me` unsupported. |

## Frontend boot

| New work | Analog | Location |
|----------|--------|----------|
| Provider gate | `window.onload` Plex pin block | `templates/index.html` ~808–829 |
| Jellyfin login | `loginWithPlex()` jellyfin branch | `templates/index.html` ~382–405 |

## Dual HTML

| File | Role |
|------|------|
| `templates/index.html` | Canonical server-rendered UI |
| `data/index.html` | PWA-oriented duplicate — **must receive identical Phase 9 edits** |

---

## PATTERN MAPPING COMPLETE
