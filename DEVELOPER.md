# Developer Guide

This guide explains how to set up and work on Jellyswipe as it exists today: a
FastAPI app with a static HTML/CSS/JavaScript frontend served from the Python
package.

## Prerequisites

Install these before working on the app:

- `uv` for Python dependency management and command execution.
- Docker for container builds and production-style local runs.
- Git.

You also need Jellyfin and TMDB credentials for realistic local development:

- `JELLYFIN_URL`
- `JELLYFIN_API_KEY`
- `TMDB_ACCESS_TOKEN`
- `SESSION_SECRET`

Do not commit secrets, `.env` files, local database files, API keys, or tokens.
The repo already ignores `.env` and the default local database path.

## How This Project Uses uv

This is a `uv`-managed Python project. Avoid bare `python`, `pip`, `pytest`,
`ruff`, or `alembic` commands when working in this repo.

Use these patterns instead:

- `uv sync` installs project dependencies into a repo-local virtual environment.
- `uv run ...` runs a command inside that environment.
- `uv add <package>` adds a runtime dependency and updates project metadata.
- `uv add --dev <package>` adds a development dependency.
- `uv lock` updates the lockfile after dependency changes.

You do not need to manually activate `.venv` for normal project commands.

## First-Time Setup

Install dependencies from the committed lockfile:

```bash
uv sync --frozen
```

Create the local data directory used by the default SQLite database:

```bash
mkdir -p data
```

Create a local `.env` file:

```env
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_API_KEY=your-jellyfin-api-key
TMDB_ACCESS_TOKEN=your-tmdb-read-access-token
SESSION_SECRET=replace-with-a-long-random-string

# Useful for local/private Jellyfin URLs such as LAN IPs, localhost, or host.docker.internal.
ALLOW_PRIVATE_JELLYFIN=1
```

Optional local-only settings:

```env
# Defaults to data/jellyswipe.db when omitted.
DB_PATH=data/jellyswipe.db

# Optional stable Jellyfin device ID.
JELLYFIN_DEVICE_ID=jelly-swipe-dev
```

If you use a custom `DB_PATH`, make sure the parent directory exists and the
database file is not committed.

## Running Locally With uv

Start the app:

```bash
uv run python -m jellyswipe.bootstrap
```

The app listens on `http://localhost:5005`.

Useful local URLs:

- App: `http://localhost:5005/`
- OpenAPI docs: `http://localhost:5005/docs`
- ReDoc: `http://localhost:5005/redoc`
- Raw OpenAPI JSON: `http://localhost:5005/openapi.json`
- Liveness check: `http://localhost:5005/healthz`
- Readiness check: `http://localhost:5005/readyz`

Startup applies Alembic migrations before serving requests. You normally do not
need to run migrations manually just to start the app.

## Tests, Linting, and Formatting

Run the full test suite:

```bash
uv run pytest tests/
```

Run one test file:

```bash
uv run pytest tests/test_routes_room.py -v
```

Run Ruff linting:

```bash
uv run ruff check .
```

Format Python files:

```bash
uv run ruff format .
```

If you change the database schema, create a new Alembic revision instead of
editing the baseline migration:

```bash
uv run alembic revision --autogenerate -m "short description"
uv run alembic upgrade head
```

Never modify `alembic/versions/0001_phase36_baseline.py`.

## Pre-Commit Hooks

This repo has `.pre-commit-config.yaml` with Ruff, Ruff format, Prettier, YAML
checks, debug statement checks, end-of-file fixes, and trailing whitespace fixes.

Install the Git hooks:

```bash
uv tool run pre-commit install
```

Run all hooks manually:

```bash
uv tool run pre-commit run --all-files
```

Run hooks against staged changes only:

```bash
uv tool run pre-commit run
```

If `uv tool run pre-commit ...` downloads `pre-commit` the first time, that is
expected. `pre-commit` is tool-managed rather than a project runtime dependency.

## Docker Development

Build a local development image:

```bash
docker build -t jelly-swipe:dev .
```

Run the container with required environment variables and port forwarding:

```bash
docker run --rm \
  --name jelly-swipe-dev \
  -p 5005:5005 \
  -e JELLYFIN_URL=http://your-jellyfin-host:8096 \
  -e JELLYFIN_API_KEY=your-jellyfin-api-key \
  -e TMDB_ACCESS_TOKEN=your-tmdb-read-access-token \
  -e SESSION_SECRET=replace-with-a-long-random-string \
  -e ALLOW_PRIVATE_JELLYFIN=1 \
  jelly-swipe:dev
```

For Docker runs, remember that `localhost` inside the container means the
container itself. If Jellyfin is running on your host machine, use a LAN address
or `host.docker.internal` where supported.

This dev command intentionally does not mount a volume. The SQLite database is
ephemeral inside the container and disappears when the container is removed.

## Database Notes

The app uses SQLAlchemy 2.x and Alembic.

Important rules:

- Runtime database writes should go through `DatabaseUnitOfWork`.
- Do not add new raw `sqlite3` application code.
- Tests bootstrap schema through Alembic.
- Schema changes require SQLAlchemy model updates and a new Alembic revision.
- Public API payloads use `media_id`, not `movie_id`.

## Static Frontend Notes

Current frontend files:

- `jellyswipe/templates/index.html`
- `jellyswipe/static/app.js`
- `jellyswipe/static/styles.css`
- `jellyswipe/static/manifest.json`
- `jellyswipe/static/sw.js`
- `jellyswipe/static/*` image and icon assets

FastAPI serves:

- `/` from the Jinja template.
- `/static/*` from `jellyswipe/static/`.
- `/manifest.json`, `/sw.js`, and `/favicon.ico` from explicit routes.

Keep PWA behavior in mind when changing static files.

## Production Static-Serving Validation

Before merging frontend or static asset changes to `main`, verify the production
serving path rather than only checking files directly in the browser.

For the current static frontend:

1. Run the app with `uv run python -m jellyswipe.bootstrap`.
2. Open `http://localhost:5005/`.
3. Confirm the page loads through FastAPI, not from a local file path.
4. Confirm `/static/app.js`, `/static/styles.css`, `/manifest.json`, `/sw.js`,
   and `/favicon.ico` return successfully.
5. Exercise the affected UI flow in the browser.

For Docker validation:

1. Build the image with `docker build -t jelly-swipe:dev .`.
2. Run it with the required environment variables and `-p 5005:5005`.
3. Open `http://localhost:5005/`.
4. Confirm the UI and API are served from the same container.
5. Confirm `http://localhost:5005/healthz` returns a healthy response.

When the React frontend is added later, update this section with the selected
frontend build command and the exact location where built assets are emitted for
FastAPI to serve.

## CI Checks

Pull requests run:

- PR title linting with semantic/conventional title rules.
- `uv sync --frozen`.
- `scripts/phase40_val04_guard.sh`.
- `uv run pytest tests/`.
- Unraid template lint when `unraid_template/jelly-swipe.html` changes.

Main and release image publishing workflows build Docker images separately.

## Commit Messages and PR Titles

This repo uses [Conventional Commits](https://www.conventionalcommits.org/).
Conventional format is required for PR titles and strongly expected for commits.

Use this shape:

```text
<type>(optional-scope): short imperative summary
```

Allowed PR title types are:

- `feat`
- `fix`
- `docs`
- `chore`
- `refactor`
- `test`
- `ci`
- `build`
- `perf`
- `revert`

Good examples:

- `docs: add developer setup guide`
- `fix(auth): clear expired session cookie`
- `feat(room): support tv show deck creation`
- `test(routes): cover room setup validation`
- `build(docker): copy frontend assets into image`

Avoid vague messages:

- `updates`
- `fix stuff`
- `work in progress`
- `changes`

## PR Message Guidelines

A good PR description should include:

- What changed.
- Why the change is needed.
- How you tested it.
- Screenshots or screen recordings for UI changes.
- Any follow-up work intentionally left out.
- Links to related issues, PRDs, ADRs, or design notes.

Use links when possible:

- `Closes #123`
- `Refs #123`
- `Refs docs/prd/004-session-match-mutation.md`
- `Refs docs/adr/0002-operational-hardening-conventions.md`

For frontend PRs, include mobile screenshots when the change affects layout or
user flows.

## Dependency Changes

Use `uv` to change Python dependencies:

```bash
uv add package-name
uv add --dev package-name
```

Commit both `pyproject.toml` and `uv.lock` after dependency changes.

Do not hand-edit `uv.lock`.

## Local Troubleshooting

If startup fails because the SQLite database cannot be opened, create the data
directory:

```bash
mkdir -p data
```

If startup rejects a local or private Jellyfin URL, set:

```env
ALLOW_PRIVATE_JELLYFIN=1
```

If dependencies do not match CI, resync from the lockfile:

```bash
uv sync --frozen
```

If Docker cannot reach Jellyfin at `localhost`, use a LAN IP or
`host.docker.internal` instead.
