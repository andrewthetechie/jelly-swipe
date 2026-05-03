# Phase 33: Router Extraction and Endpoint Parity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 33-router-extraction-and-endpoint-parity
**Areas discussed:** Shared state migration, Router-to-route mapping, Helper function placement, Swipe transaction integrity

---

## Shared State Migration

| Option | Description | Selected |
|--------|-------------|----------|
| Import from __init__ | Routers do `from jellyswipe import TMDB_AUTH_HEADERS` — same as get_provider() lazy import | |
| Move globals to a config module | Create jellyswipe/config.py holding all shared globals | ✓ |
| Use app.state | Attach globals to app.state during lifespan; access via request.app.state | |

**User's choice:** Move globals to a config module
**Notes:** User chose the cleanest separation — all shared state in one place.

| Question | Selected |
|----------|----------|
| Should _token_user_id_cache move to config.py? | ✓ Move cache to config.py |
| When should config.py globals be initialized? | ✓ Import-time in config.py |
| Should SSRF validation and JELLYFIN_URL move to config.py? | ✓ Yes, move both to config.py |

---

## Router-to-Route Mapping

| Route | Decision |
|-------|----------|
| /genres → routers/media.py | ✓ Media domain (Jellyfin provider query) |
| /matches + /matches/delete → routers/rooms.py | ✓ Room-scoped data |
| /me → routers/auth.py | ✓ Session identity endpoint |
| /jellyfin/server-info → routers/auth.py | ✓ Auth-adjacent |
| /plex/server-info | Deleted (dead code, returns 410 Gone) |

**Notes:** User explicitly chose to delete the dead Plex route during extraction rather than carry it forward.

---

## Helper Function Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in routers/rooms.py | Room-domain helpers, private to the only router that uses them | ✓ |
| Move to jellyswipe/db.py | DB-layer concern but would blur layer boundary | |
| Create jellyswipe/utils.py | Overkill for 3 functions used by one router | |

**User's choice:** Inline in routers/rooms.py

---

## Swipe Transaction Integrity

| Question | Selected |
|----------|----------|
| How guarantee transaction logic survives? | ✓ Verbatim copy + test |
| Switch to DBConn dependency? | ✓ Yes, use DBConn (fixes CR-01 connection leak) |

**Notes:** Verbatim copy with comment marking critical logic. Switching to DBConn fixes the connection leak identified in Phase 31 code review (CR-01).

---

## Agent's Discretion

- Router file organization (imports ordering, docstring style) — follow existing patterns
- Whether `_APP_ROOT` stays in `__init__.py` or moves to `config.py`
- Rate limit wiring approach (inline vs router-level dependency)
- Error logging pattern in extracted routes

## Deferred Ideas

None — discussion stayed within phase scope.
