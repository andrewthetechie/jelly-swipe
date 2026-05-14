# Jellyswipe — Agent Instructions

Jellyswipe is a Jellyfin-based media swiping app. Users join or create a room, swipe left/right on movie and TV show cards fetched from a Jellyfin server, and a match fires when both participants swipe right on the same item. The app supports solo sessions and hosted two-user sessions.

## Command Policy

- Treat this as a `uv`-managed Python project. Do not assume global `python`, `pip`, `pytest`, `ruff`, or `alembic`.
- Always prefer `uv run ...` for project commands and `uv sync` for first-time setup.
- Default test command: `uv run pytest tests/`
- Single test file: `uv run pytest tests/test_routes_room.py -v`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Run the app locally: `uv run python -m jellyswipe.bootstrap`
- Do not use bare `pytest`, bare `ruff`, bare `alembic`, or `python -m pytest` unless the user explicitly asks for it.

## Architecture

```text
jellyswipe/
├── routers/         FastAPI route handlers
├── services/        Business logic
├── repositories/    SQLAlchemy data access
├── models/          SQLAlchemy ORM models
├── jellyfin_library.py
├── config.py
├── db.py
├── db_runtime.py
├── db_uow.py
└── static/app.js    Frontend logic, no build step
```

- Entry point: `jellyswipe/__init__.py` builds the FastAPI app and registers routers.
- The app is a package, not a loose script. Use `uv run python -m jellyswipe.bootstrap`.
- Frontend changes normally live in `jellyswipe/static/app.js` and `jellyswipe/static/styles.css`.

## Database Rules

- This repo uses SQLAlchemy 2.x plus Alembic. Do not treat it as a raw `sqlite3` project.
- Application/runtime database access should use SQLAlchemy async sessions from `jellyswipe.db_runtime` and the `DatabaseUnitOfWork` in `jellyswipe.db_uow`.
- All DB writes go through `DatabaseUnitOfWork`. Do not instantiate repositories directly outside a managed session/UoW boundary.
- Do not add new raw `sqlite3` application code. The existing direct `sqlite3` helpers are test-only utilities in `tests/conftest.py`.
- If schema changes are needed, update the SQLAlchemy models and create a new Alembic revision in `alembic/versions/`.
- Create migrations with `uv run alembic revision --autogenerate -m "short description"`.
- Apply migrations with `uv run alembic upgrade head`.
- Never modify `alembic/versions/0001_phase36_baseline.py`. Add a new numbered revision instead.
- Tests bootstrap schema through Alembic. Do not hand-roll tables in tests when the migration path should own the schema.

Example write pattern:

```python
async with runtime_sessionmaker() as session:
    uow = DatabaseUnitOfWork(session)
    result = await service.create_room(session_dict, user_id, provider, uow)
    await session.commit()
```

## API and Service Conventions

- Always use `XSSSafeJSONResponse` for JSON API responses. Do not use `JSONResponse` directly.
- Authenticated routes should use `require_auth`.
- `DeckProvider` is defined in `jellyswipe/services/room_lifecycle.py`. Production uses `JellyfinLibrary`; tests usually use `FakeProvider`.
- `fetch_deck` takes `media_types: list[str]` containing `"movie"` and/or `"tv_show"`.
- Public API payloads use `media_id`, not `movie_id`.
- `POST /room` expects JSON booleans for `movies`, `tv_shows`, and `solo`. String booleans should be rejected.

## Domain Notes

- `Room.pairing_code` is the 4-digit join code.
- `Room.solo_mode` distinguishes solo from hosted sessions.
- `Room.include_movies` and `Room.include_tv_shows` are immutable after room creation.
- `Room.ready` means the room accepts swipes.
- `Room.current_genre` uses `"All"` to mean no filter.
- `Room.deck_position_json` stores per-user cursors.
- `Room.movie_data_json` stores the current deck card payloads.

Card dict shape:

```python
{
    "id": str,
    "title": str,
    "summary": str,
    "thumb": str,
    "year": int | None,
    "media_type": str,
    "rating": float | None,
    "duration": str | None,
    "season_count": int | None,
}
```

## Testing Conventions

- Use `@pytest.mark.anyio` for async tests.
- `tests/conftest.py` provides important fixtures including `runtime_sessionmaker` and `client_real_auth`.
- Mock Jellyfin with `FakeProvider` or `mocker.patch`.
- Prefer targeted runs while iterating, but when reporting verification use the exact command you ran.
- If you say you ran tests, include whether it was `uv run pytest tests/` or a narrower `uv run pytest tests/...`.
- Test names should describe behavior, for example `test_create_room_with_tv_shows_sets_include_tv_shows`.

## Environment Variables

- Required: `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `TMDB_ACCESS_TOKEN`, `SESSION_SECRET`
- Optional: `DB_PATH`, `JELLYFIN_DEVICE_ID`, `ALLOW_PRIVATE_JELLYFIN`
- Use `SESSION_SECRET`, not `FLASK_SECRET`.

## Git and Commit Hygiene

- Use explicit `git add <file>` paths. Never use `git add .` or `git add -A`.
- Do not commit orchestration or local-index state:
  - `.orchestra/`
  - `opencode.json`, `.opencode/`
  - `.serena/`
  - `ORCH_DISPATCH_*.md`
  - `.gitnexus/`

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **jelly-swipe**. Use GitNexus to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` first.

## Always Do

- Before modifying a function, class, or method, run impact analysis on the target symbol and report the blast radius to the user.
- Run change detection before committing to verify only expected symbols and execution flows changed.
- Warn the user before proceeding if impact analysis reports HIGH or CRITICAL risk.
- When exploring unfamiliar code, prefer GitNexus execution-flow queries over blind grepping.

## Never Do

- Never edit a function, class, or method without first running impact analysis on that symbol.
- Never ignore HIGH or CRITICAL impact warnings.
- Never rename symbols with find-and-replace when GitNexus rename support is available.
- Never commit without checking the affected scope with GitNexus change detection.

## Resources

- `gitnexus://repo/jelly-swipe/context`
- `gitnexus://repo/jelly-swipe/clusters`
- `gitnexus://repo/jelly-swipe/processes`
- `gitnexus://repo/jelly-swipe/process/{name}`

## Skill Pointers

- Architecture and execution flow: `gitnexus-exploring`
- Impact analysis: `gitnexus-impact-analysis`
- Debugging: `gitnexus-debugging`
- Refactoring: `gitnexus-refactoring`
- Tooling reference: `gitnexus-guide`
- CLI workflows: `gitnexus-cli`
<!-- gitnexus:end -->
