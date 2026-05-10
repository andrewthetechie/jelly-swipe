# Jellyswipe — Agent Instructions

Jellyswipe is a Jellyfin-based media swiping app. Users join or create a room, swipe left/right on movie and TV show cards fetched from a Jellyfin server, and a match fires when both participants swipe right on the same item. Supports solo sessions (single user) and hosted sessions (two users).

## Running Tests and Lint

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_routes_room.py -v

# Ruff lint (must pass before committing)
ruff check .
ruff format .

Pre-commit hooks run ruff and prettier automatically on every git commit. Do not skip them.

Architecture

jellyswipe/
├── routers/        # FastAPI route handlers (rooms, media, auth, proxy, static)
├── services/       # Business logic (RoomLifecycleService, SwipeMatchService)
├── repositories/   # SQLAlchemy DB access (rooms, swipes, matches)
├── models/         # SQLAlchemy ORM models (Room, Swipe, Match, AuthSession)
├── jellyfin_library.py  # Jellyfin REST client + JellyfinLibraryProvider
├── config.py       # Env-var config, singleton provider
├── auth.py         # Auth + session management
├── db_uow.py       # Unit of Work pattern for transactional DB access
└── static/app.js   # All frontend logic (single JS file, no build step)

Entry point: jellyswipe/__init__.py creates the FastAPI app and registers routers.

Database: SQLite via SQLAlchemy + Alembic. Migrations live in alembic/versions/. Always create a new numbered revision file — never modify 0001_phase36_baseline.py.

Key Patterns

Unit of Work

All DB writes go through DatabaseUnitOfWork. Never access repositories directly outside a uow context:

async with runtime_sessionmaker() as session:
    uow = DatabaseUnitOfWork(session)
    result = await service.create_room(session_dict, user_id, provider, uow)
    await session.commit()

JSON Responses

Always use XSSSafeJSONResponse for API responses. Never use JSONResponse directly.

Auth

Route handlers that require auth use the require_auth FastAPI dependency:

async def my_endpoint(request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)):

DeckProvider Protocol

DeckProvider is a protocol defined in services/room_lifecycle.py. Production implementation is JellyfinLibrary in jellyfin_library.py. Tests use FakeProvider. The fetch_deck signature:

def fetch_deck(self, media_types: List[str], genre_name: Optional[str] = None) -> List[dict]

media_types is a list containing "movie" and/or "tv_show".

Room Model — Key Fields

- pairing_code — 4-digit code users share to join
- solo_mode — True for single-user sessions
- include_movies, include_tv_shows — immutable after creation
- ready — True when the room accepts swipes
- current_genre — active genre filter ("All" = no filter)
- deck_position_json — {user_id: cursor_position}
- movie_data_json — JSON array of card dicts for the current deck

Card Dict Shape

{
    "id": str,            # Jellyfin item ID
    "title": str,
    "summary": str,
    "thumb": str,         # Proxied URL via /proxy endpoint
    "year": int | None,
    "media_type": str,    # "movie" or "tv_show"
    # movies only:
    "rating": float | None,
    "duration": str | None,
    # tv_show only:
    "season_count": int | None,
}

Public API Field Names

- media_id (not movie_id) in all request/response bodies — renamed in ORCH-003.
- movies, tv_shows, solo in POST /room body must be JSON booleans, not strings. Returns 400 otherwise.

Endpoint Summary

┌────────┬──────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Method │         Path         │                                                   Description                                                   │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ POST   │ /room                │ Create room. Body: {"movies": bool, "tv_shows": bool, "solo": bool}. Empty body defaults to movies-only hosted. │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ POST   │ /room/solo           │ Removed — 404. Use POST /room with {"solo": true}.                                                              │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ POST   │ /room/{code}/join    │ Join an existing room                                                                                           │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ POST   │ /room/{code}/swipe   │ Swipe. Body: {"media_id": str, "direction": str}                                                                │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ GET    │ /room/{code}/deck    │ Get next card(s) for the user                                                                                   │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ POST   │ /room/{code}/go-solo │ Removed — 404                                                                                                   │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ GET    │ /media/genres        │ List available genres from Jellyfin                                                                             │
├────────┼──────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ GET    │ /me                  │ Current session info                                                                                            │
└────────┴──────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Migrations

# Create a new migration (after editing models)
uv run alembic revision --autogenerate -m "short description"

# Apply migrations
uv run alembic upgrade head

Never edit the baseline migration. All schema changes go in new numbered revision files.

Testing Conventions

- @pytest.mark.anyio for async tests
- conftest.py provides runtime_sessionmaker and client_real_auth fixtures
- Mock Jellyfin calls with FakeProvider or mocker.patch
- Test names describe the behaviour: test_create_room_with_tv_shows_sets_include_tv_shows
- Use explicit git add <file> paths — never git add . or git add -A

Files That Must Never Be Committed

These are managed by the orch orchestration system and are in .gitignore:

- .orchestra/ — orchestration state
- opencode.json, .opencode/ — opencode agent config
- .serena/ — Serena project index
- ORCH_DISPATCH_*.md — agent dispatch payloads
- .gitnexus/ — GitNexus knowledge graph

Environment Variables

┌────────────────────┬──────────┬───────────────────────────────────────────────────────────────┐
│      Variable      │ Required │                          Description                          │
├────────────────────┼──────────┼───────────────────────────────────────────────────────────────┤
│ JELLYFIN_URL       │ Yes      │ Base URL of the Jellyfin server                               │
├────────────────────┼──────────┼───────────────────────────────────────────────────────────────┤
│ JELLYFIN_API_KEY   │ Yes      │ Admin API key                                                 │
├────────────────────┼──────────┼───────────────────────────────────────────────────────────────┤
│ FLASK_SECRET       │ Yes      │ Session secret key                                            │
├────────────────────┼──────────┼───────────────────────────────────────────────────────────────┤
│ DB_PATH            │ No       │ SQLite path (default: app data dir)                           │
├────────────────────┼──────────┼───────────────────────────────────────────────────────────────┤
│ JELLYFIN_DEVICE_ID │ No       │ Device ID sent to Jellyfin (default: jelly-swipe-jellyfin-v1) │
└────────────────────┴──────────┴───────────────────────────────────────────────────────────────┘

Dependency Notes

- requests (sync) for Jellyfin API calls — JellyfinLibrary uses requests.Session
- aiosqlite for async SQLite in tests
- sse-starlette for Server-Sent Events on the match notification stream
- No frontend build step — static/app.js is vanilla JS served directly

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **jelly-swipe** (2393 symbols, 4768 relationships, 119 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/jelly-swipe/context` | Codebase overview, check index freshness |
| `gitnexus://repo/jelly-swipe/clusters` | All functional areas |
| `gitnexus://repo/jelly-swipe/processes` | All execution flows |
| `gitnexus://repo/jelly-swipe/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
```
