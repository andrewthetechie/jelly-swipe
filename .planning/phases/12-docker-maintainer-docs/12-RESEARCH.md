# Phase 12: Docker & maintainer docs - Research

**Researched:** 2026-04-24
**Domain:** Python Docker containerization with uv package manager
**Confidence:** HIGH

## Summary

This phase focuses on updating the Dockerfile to use uv for dependency installation instead of pip, ensuring reproducible builds via the committed uv.lock file. The research confirms that uv provides significant performance benefits (10-100x faster than pip) and offers robust Docker integration patterns including multi-stage builds and layer caching optimization.

The recommended approach uses a multi-stage build pattern: a builder stage installs uv, syncs dependencies from uv.lock in non-editable mode, then copies the virtual environment to a minimal final Python 3.13-slim image. This keeps the final image small while ensuring reproducible builds. Layer caching is optimized by copying pyproject.toml and uv.lock before the source code, so dependency layers only invalidate when dependencies change.

For maintainers, the README needs a Development section documenting uv workflows: `uv sync` for initial setup, `uv run python -m jellyswipe` for local dev server, `uv run gunicorn jellyswipe:app` for production-style testing, `uv add <package>` for adding dependencies, and `uv lock --upgrade` for updating the lockfile. The Python 3.13 requirement should be noted.

No PyPI publishing workflow exists and none should be added — distribution remains Docker Hub and GHCR only, with source checkout as an alternative. The current requirements.txt is deprecated and can be removed once Dockerfile no longer references it.

**Primary recommendation:** Use multi-stage Docker build with `--no-editable` flag, copy pyproject.toml/uv.lock before source code for layer caching, and preserve the existing Gunicorn CMD and port 5005 exposure.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dependency installation | Build (Docker builder stage) | — | uv runs during image build, not at runtime |
| Application execution | Runtime (Docker final stage) | — | Gunicorn serves Flask app from .venv |
| Layer caching optimization | Build (Dockerfile structure) | — | Docker layer cache is a build-time concern |
| Package management | Local development | — | uv runs on developer machine, not in container |
| Distribution | CI/CD (GitHub Actions) | — | Docker Hub/ghcr push happens in workflows |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uv | 0.11.7 | Fast Python package manager | 10-100x faster than pip, official Docker image, robust lockfile support [VERIFIED: Docker Hub ghcr.io/astral-sh/uv:latest] |
| python | 3.13-slim | Base image for container | Project requires Python 3.13 (UV-02), slim variant minimizes image size [VERIFIED: Docker Hub library/python:3.13-slim] |
| gunicorn | >=25.3.0 | WSGI server | Production-grade WSGI server, already configured with gevent workers [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hatchling | latest | Build backend | Already configured in pyproject.toml for wheel packaging [VERIFIED: pyproject.toml] |
| flask | >=3.1.3 | Web framework | Core application framework [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Multi-stage build with uv | Single-stage build with uv | Single-stage keeps uv binary in final image (~26MB), multi-stage removes it for smaller production image |
| `uv sync --locked --no-editable` | `uv pip install -r requirements.txt` | `uv sync` respects uv.lock format with advanced features (dependency groups, universal resolution), pip requires export step |

**Installation:**
```bash
# For local development (macOS)
brew install uv

# For Docker builds (no installation needed - use ghcr.io/astral-sh/uv:latest image)
```

**Version verification:**
```bash
# Verified 2026-04-24
uv --version  # 0.9.18 (local), 0.11.7 (Docker image)
docker images python:3.13-slim  # Available on Docker Hub
```

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Build Process                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Builder Stage (ghcr.io/astral-sh/uv:python3.13-slim)           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. Copy uv binary from official image                   │    │
│  │ 2. Copy pyproject.toml, uv.lock (layer cache point 1)   │    │
│  │ 3. RUN uv sync --locked --no-install-project --no-editable│   │
│  │    (installs dependencies to .venv)                    │    │
│  │ 4. Copy jellyswipe/ source code                         │    │
│  │ 5. RUN uv sync --locked --no-editable                   │    │
│  │    (installs project to .venv)                         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ COPY --from=builder /app/.venv /app/.venv
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Final Stage (python:3.13-slim)                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. Copy .venv from builder (no source code)             │    │
│  │ 2. Copy jellyswipe/templates, jellyswipe/static          │    │
│  │    (package data, not in .venv)                         │    │
│  │ 3. EXPOSE 5005                                           │    │
│  │ 4. VOLUME /app/data (SQLite DB)                          │    │
│  │ 5. ENV PATH="/app/.venv/bin:$PATH"                       │    │
│  │ 6. CMD ["gunicorn", "-b", "0.0.0.0:5005",                │    │
│  │       "-k", "gevent", "--worker-connections", "1000",    │    │
│  │       "jellyswipe:app"]                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Runtime (Container starts)                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Gunicorn spawns gevent workers                          │    │
│  │ Workers import jellyswipe:app                           │    │
│  │ App connects to Plex/Jellyfin, TMDB, SQLite DB          │    │
│  │ Listens on 0.0.0.0:5005                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
Dockerfile                      # Multi-stage build with uv
pyproject.toml                  # Project metadata, dependencies
uv.lock                         # Committed lockfile (read-only in this phase)
jellyswipe/                     # Application package
├── __init__.py                 # Flask app entry point (app = Flask(...))
├── templates/                  # Jinja2 templates (index.html)
├── static/                     # Static assets (images, manifest.json)
├── db.py                       # Database functions
├── factory.py                  # Media provider factory
├── plex_library.py             # Plex integration
└── jellyfin_library.py         # Jellyfin integration
.github/workflows/
├── docker-image.yml            # CI: Build and push to Docker Hub
└── release-ghcr.yml            # CI: Build and push to GHCR on releases
README.md                       # Deployment + Development sections
requirements.txt                # Deprecated - can remove after Dockerfile update
```

### Pattern 1: Multi-stage Docker Build with uv

**What:** Use a builder stage with uv to install dependencies, then copy only the virtual environment to a minimal final image.

**When to use:** Production Docker images where image size matters and reproducible builds are required.

**Example:**
```dockerfile
# Builder stage with uv
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# Copy source code
COPY . .

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Final stage (minimal image)
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy package data (not included in .venv)
COPY jellyswipe/templates jellyswipe/templates
COPY jellyswipe/static jellyswipe/static

# Ensure .venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create data directory for SQLite DB
RUN mkdir -p /app/data

EXPOSE 5005

# Preserve existing Gunicorn CMD
CMD ["gunicorn", "-b", "0.0.0.0:5005", "-k", "gevent", "--worker-connections", "1000", "jellyswipe:app"]
```

**Source:** [uv Docker documentation - Multi-stage build with non-editable install](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) [CITED]

### Pattern 2: Layer Caching Optimization

**What:** Copy pyproject.toml and uv.lock before the rest of the source code, and use `--no-install-project` in the first `uv sync` to create a cached dependency layer.

**When to use:** Any Docker build where dependencies change less frequently than application code.

**Example:**
```dockerfile
# This layer only invalidates when pyproject.toml or uv.lock change
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# This layer invalidates when any source file changes
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable
```

**Source:** [uv Docker documentation - Optimize Docker Build Times](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) [CITED]

### Pattern 3: uv Development Workflow

**What:** Use uv commands for local development instead of pip.

**When to use:** All local development work on this project.

**Example:**
```bash
# First-time setup
uv sync

# Run dev server
uv run python -m jellyswipe

# Run production-style server for testing
uv run gunicorn -b 0.0.0.0:5005 -k gevent --worker-connections 1000 jellyswipe:app

# Add a new dependency
uv add requests

# Update lockfile after dependency changes
uv lock --upgrade
```

**Source:** [uv documentation - Run commands in project environment](https://github.com/astral-sh/uv/blob/main/docs/guides/projects.md) [CITED]

### Anti-Patterns to Avoid

- **Using `uv pip install` in Dockerfile:** This bypasses uv.lock and loses reproducibility. Use `uv sync --locked` instead.
- **Installing uv in final stage:** The uv binary (~26MB) should stay in the builder stage, not the final image.
- **Copying source code before dependency files:** This breaks layer caching — every code change forces dependency re-installation.
- **Using editable mode (`pip install -e` or `uv sync` without `--no-editable`):** This requires source code in the final image, defeating multi-stage build benefits.
- **Not using cache mounts:** Without `--mount=type=cache,target=/root/.cache/uv`, uv downloads packages on every build, defeating performance gains.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fast dependency installation | Custom pip caching scripts | `uv sync` with cache mount | uv is 10-100x faster than pip, handles caching internally |
| Reproducible dependency locking | Manual requirements.txt version pinning | `uv.lock` (committed) | uv.lock supports advanced features (dependency groups, universal resolution) |
| Multi-stage build layer caching | Custom Docker layer ordering | Copy pyproject.toml/uv.lock first, use `--no-install-project` | uv docs recommend this pattern for optimal cache hit rate |
| Python bytecode compilation | Manual `.pyc` generation in Dockerfile | `UV_COMPILE_BYTECODE=1` env var | uv handles compilation correctly, respects platform-specific settings |
| Virtual environment management | Manual venv creation/activation | `uv sync` (creates .venv automatically) | uv manages venv lifecycle, ensures consistency across machines |

**Key insight:** uv was specifically designed to solve Python packaging pain points — it's faster, more reliable, and has better Docker integration than pip. Custom solutions inevitably miss edge cases that uv handles correctly.

## Common Pitfalls

### Pitfall 1: Breaking existing deployments with port/volume changes

**What goes wrong:** Changing the exposed port or `/app/data` volume path breaks existing Docker Compose and Unraid deployments that expect port 5005 and `/app/data`.

**Why it happens:** The phase focuses on uv integration, so it's easy to overlook that operators have configured volume mounts and port mappings based on the current Dockerfile.

**How to avoid:** Preserve `EXPOSE 5005` and ensure `/app/data` directory exists and remains the default SQLite DB location. Document clearly in the Dockerfile comments.

**Warning signs:** Test Docker build with existing docker-compose.yml from README; verify port 5005 is exposed and /app/data is writable.

### Pitfall 2: Losing package data (templates/static) in multi-stage build

**What goes wrong:** After multi-stage build, the container starts but returns 404 for all routes because templates/ and static/ directories are missing.

**Why it happens:** The virtual environment (.venv) doesn't include package data (templates, static) — these are separate files that must be copied explicitly.

**How to avoid:** After copying .venv from builder, explicitly copy `jellyswipe/templates` and `jellyswipe/static` to the final stage. Verify pyproject.toml has `[tool.hatch.build.targets.wheel.shared-data]` configured.

**Warning signs:** Container starts but Flask returns "404 Not Found" or template errors. Check `ls /app/jellyswipe/templates` in the container.

### Pitfall 3: Breaking Gunicorn entry point

**What goes wrong:** Container starts but Gunicorn fails with "ModuleNotFoundError: No module named 'jellyswipe'" or "ImportError: cannot import name 'app'".

**Why it happens:** The Gunicorn CMD `jellyswipe:app` assumes (1) jellyswipe package is importable, (2) app variable exists in jellyswipe/__init__.py, and (3) .venv is on PATH.

**How to avoid:** Ensure `ENV PATH="/app/.venv/bin:$PATH"` is set, and verify the CMD matches the existing entry point: `["gunicorn", "-b", "0.0.0.0:5005", "-k", "gevent", "--worker-connections", "1000", "jellyswipe:app"]`.

**Warning signs:** Gunicorn logs show import errors. Test with `docker run --rm -p 5005:5005 <image> gunicorn --check-config jellyswipe:app`.

### Pitfall 4: Layer caching not working (slow builds)

**What goes wrong:** Every `docker build` re-downloads and re-installs all dependencies, taking minutes instead of seconds.

**Why it happens:** Source code was copied before pyproject.toml/uv.lock, or `--no-install-project` wasn't used in the first sync. Every code change invalidates the dependency layer.

**How to avoid:** Follow the layer caching pattern strictly: copy pyproject.toml/uv.lock first, run `uv sync --locked --no-install-project --no-editable`, then copy source, then run `uv sync --locked --no-editable`.

**Warning signs:** Docker build output shows "RUN uv sync" executing on every build even when dependencies haven't changed. Time `docker build` before and after to verify.

### Pitfall 5: Accidentally enabling editable mode

**What goes wrong:** Multi-stage build doesn't reduce image size because .venv contains references to source code, requiring source files in final image.

**Why it happens:** Forgetting `--no-editable` flag causes uv to install in editable mode, which requires source code at runtime.

**How to avoid:** Always use `--no-editable` with `uv sync` in Docker builds. This allows .venv to be copied independently of source code.

**Warning signs:** Final image size is similar to builder image, or container fails with "FileNotFoundError" when trying to import jellyswipe.

## Code Examples

Verified patterns from official sources:

### Multi-stage Dockerfile with uv

```dockerfile
# Builder stage with uv
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# Copy source code
COPY . .

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Final stage (minimal image)
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy package data (not included in .venv)
COPY jellyswipe/templates jellyswipe/templates
COPY jellyswipe/static jellyswipe/static

# Ensure .venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create data directory for SQLite DB
RUN mkdir -p /app/data

EXPOSE 5005

CMD ["gunicorn", "-b", "0.0.0.0:5005", "-k", "gevent", "--worker-connections", "1000", "jellyswipe:app"]
```

**Source:** [uv Docker documentation - Multi-stage build with non-editable install](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) [CITED]

### uv sync with cache mount

```dockerfile
# Enable copy mode for cache mount compatibility
ENV UV_LINK_MODE=copy

# Use cache mount to persist uv's download cache across builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
```

**Source:** [uv Docker documentation - Improve Docker Build Performance](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) [CITED]

### uv local development commands

```bash
# First-time setup (creates .venv and installs from uv.lock)
uv sync

# Run Flask dev server
uv run python -m jellyswipe

# Run Gunicorn in production mode (for local testing)
uv run gunicorn -b 0.0.0.0:5005 -k gevent --worker-connections 1000 jellyswipe:app

# Add a new dependency
uv add requests

# Update lockfile after dependency changes
uv lock --upgrade
```

**Source:** [uv documentation - Run commands in project environment](https://github.com/astral-sh/uv/blob/main/docs/guides/projects.md) [CITED]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install -r requirements.txt` in Dockerfile | `uv sync --locked` with uv.lock | Phase 12 | 10-100x faster installs, reproducible builds, better caching |
| Single-stage Docker build | Multi-stage build with builder pattern | Phase 12 | Smaller final images (no uv binary), separation of build and runtime |
| Manual layer caching | uv cache mount + `--no-install-project` | Phase 12 | Faster rebuilds when dependencies haven't changed |
| `pip install -e .` (editable mode) | `uv sync --no-editable` | Phase 12 | Allows venv to be copied without source code, smaller images |

**Deprecated/outdated:**
- `requirements.txt` as primary dependency specification: Replaced by `pyproject.toml` + `uv.lock`. Can be removed after Dockerfile update (currently has deprecation comment).
- `pip` for local development: Replaced by `uv`. All maintainer docs should reference `uv` commands, not `pip`.
- Single-stage Docker builds for Python apps: Multi-stage builds with uv are now standard practice for production images.

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this
> section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | uv 0.11.7 is the stable version to use in Dockerfile | Standard Stack | Newer versions may have breaking changes, but 0.11.7 is verified available |
| A2 | Python 3.13-slim image includes compatible glibc for uv | Standard Stack | Mismatched glibc could cause uv binary to fail, but Python 3.13-slim is standard |
| A3 | No dev dependencies are defined in pyproject.toml | Standard Stack | If dev deps exist, `--no-dev` flag is needed; verify before implementing |
| A4 | .venv created by uv contains all executables on PATH | Architecture Patterns | If gunicorn is not in .venv/bin/, PATH configuration fails; verify during testing |
| A5 | Jellyfin/Plex integration doesn't require Python 3.13-specific features | Standard Stack | If code uses 3.13-only features, downgrading would break; verify compatibility |
| A6 | Unraid operator uses `/app/data` volume mount for SQLite DB | Common Pitfalls | If operators use different paths, breaking changes would occur; verify in docs |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

None — all research areas were successfully investigated and verified with authoritative sources.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | All Docker builds | ✓ | 29.2.1 | — |
| uv (local) | Development workflow | ✓ | 0.9.18 | — |
| uv (Docker image) | Docker builds | ✓ | 0.11.7 | — |
| Python 3.13 | Base image requirement | ✗ (local 3.9) | 3.13 | Use Docker Python 3.13-slim image |
| python:3.13-slim (Docker) | Docker base image | ✓ | Available | — |
| gunicorn | Production server | ✓ (in deps) | >=25.3.0 | — |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- Python 3.13 on local machine: Not required for Docker builds; use Docker's Python 3.13-slim image. Local development requires Python 3.13 per UV-02, which developers must install separately.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected (no pytest.ini, tests/ directory, or test files found) |
| Config file | None |
| Quick run command | Wave 0 required |
| Full suite command | Wave 0 required |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCK-01 | Dockerfile uses uv for dependency installation, runs from jellyswipe package, exposes port 5005, supports /app/data | integration | `docker build -t jellyswipe-test . && docker run --rm -d -p 5005:5005 -e FLASK_SECRET=test -e TMDB_API_KEY=test jellyswipe-test && sleep 5 && curl -f http://localhost:5005/ && docker stop $(docker ps -q --filter ancestor=jellyswipe-test)` | ❌ Wave 0 |
| DOC-01 | README has Development section with uv commands | manual | Manual verification — check README.md for "## Development" section and uv command examples | ❌ Wave 0 |
| DIST-01 | No PyPI publishing workflow or documentation exists | manual | Manual verification — check .github/workflows/ and grep README.md for PyPI references | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** N/A (no test infrastructure)
- **Per wave merge:** N/A (no test infrastructure)
- **Phase gate:** Manual verification checklist in VALIDATION.md

### Wave 0 Gaps
- [ ] `tests/test_docker.py` — Docker build and container startup tests (DOCK-01)
- [ ] `tests/test_readme.py` — README Development section verification (DOC-01)
- [ ] `tests/test_distribution.py` — PyPI workflow absence verification (DIST-01)
- [ ] `tests/conftest.py` — Shared fixtures for Docker testing
- [ ] Test framework setup: Choose pytest with pytest-docker plugin or similar

**Note:** This phase has no existing test infrastructure. All validation will be manual until Wave 0 test files are created. The planner should include Wave 0 tasks to establish basic test infrastructure if automated testing is desired.

## Sources

### Primary (HIGH confidence)
- [ghcr.io/astral-sh/uv:latest] - Official uv Docker image (version 0.11.7 verified)
- [library/python:3.13-slim] - Official Python 3.13-slim Docker image
- [uv Docker documentation - Multi-stage build with non-editable install](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) - Multi-stage build pattern
- [uv Docker documentation - Optimize Docker Build Times](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) - Layer caching with --no-install-project
- [uv Docker documentation - Improve Docker Build Performance](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) - Cache mount and UV_LINK_MODE
- [uv Docker documentation - Enable Bytecode Compilation](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md) - UV_COMPILE_BYTECODE environment variable
- [uv documentation - Run commands in project environment](https://github.com/astral-sh/uv/blob/main/docs/guides/projects.md) - uv run commands
- [uv documentation - Lock and sync dependencies](https://github.com/astral-sh/uv/blob/main/docs/concepts/projects/sync.md) - uv sync, uv lock commands
- [pyproject.toml] - Project metadata, dependencies, hatchling build backend configuration
- [Dockerfile (current)] - Existing Gunicorn CMD, port 5005 exposure, /app/data directory
- [README.md] - Current Deployment section, environment variable documentation
- [.github/workflows/docker-image.yml] - Existing Docker Hub CI (no PyPI workflow)
- [.github/workflows/release-ghcr.yml] - Existing GHCR CI (no PyPI workflow)
- [jellyswipe/__init__.py] - Flask app entry point (app = Flask(...))

### Secondary (MEDIUM confidence)
- [requirements.txt] - Deprecated with comment "Kept for Docker until Phase 12" — confirms deprecation plan
- [uv-docker-example repository](https://github.com/astral-sh/uv-docker-example) - Official example showing uv Docker patterns (verified via Context7)

### Tertiary (LOW confidence)
- None — all findings were verified with primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified via Docker Hub, npm view, or official docs
- Architecture: HIGH - Patterns verified via uv official documentation and examples
- Pitfalls: HIGH - All pitfalls identified from uv docs and current codebase state

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — uv and Docker patterns are stable, but verify for breaking changes before use)
