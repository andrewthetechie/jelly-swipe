# Phase 12: Docker & maintainer docs - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Update **`Dockerfile`** to use **uv** for dependency installation with the committed lockfile, document **uv**-based setup in **`README.md`** for maintainers/contributors, and ensure no **PyPI** publishing narrative exists (distribution remains Docker Hub / GHCR only).

**Explicitly out of this phase:** Changing product behavior, adding new features, or modifying GitHub Actions beyond what's needed for uv Docker builds.
</domain>

<decisions>
## Implementation Decisions

### Dockerfile uv integration

- **D-01:** Use **multi-stage build with builder pattern**: install uv via pip in a builder stage, package jellyswipe into a wheel, then in the final stage copy the wheel, install it, and delete the wheel (keeps final image small).
- **D-02:** In the builder stage, use **`uv sync`** from the committed **`uv.lock`** file to install dependencies (ensures reproducibility per Phase 10 UV-01).
- **D-03:** Copy **`pyproject.toml`** and **`uv.lock`** early in the Dockerfile, run **`uv sync`**, then copy the rest of the source code and run a second **`uv sync`** (optimizes layer caching for faster rebuilds when dependencies haven't changed).
- **D-04:** Final image keeps the same Gunicorn CMD as Phase 11: `["gunicorn", "-b", "0.0.0.0:5005", "-k", "gevent", "--worker-connections", "1000", "jellyswipe:app"]`.
- **D-05:** Expose port **5005** and ensure **`/app/data`** directory behavior remains compatible with existing compose/Unraid operator volume mounts.

### README development documentation

- **D-06:** Add a new **"Development"** section to **`README.md`** after the existing **"Deployment"** section (clear separation between operator-facing and maintainer-facing docs).
- **D-07:** Document the following **uv** commands in the Development section:
  - **`uv sync`** — Install dependencies from uv.lock (first-time setup)
  - **`uv run python -m jellyswipe`** — Run dev server locally
  - **`uv run gunicorn jellyswipe:app`** — Run production-style server locally for testing
  - **`uv add <package>`** — Add new dependencies
  - **`uv lock --upgrade`** — Update lockfile after dependency changes
- **D-08:** Development section should include a brief note about Python 3.13 requirement (matches Phase 10 UV-02).

### PyPI story avoidance

- **D-09:** Do **not** add any PyPI publishing workflow to **`.github/workflows/`** (existing `docker-image.yml` and `release-ghcr.yml` remain Docker-only).
- **D-10:** Do **not** add any documentation implying **`pip install jellyswipe`** from PyPI (all install paths remain Docker or source checkout).

### the agent's Discretion

- Exact Dockerfile layer ordering and COPY commands (as long as D-03 caching strategy is preserved)
- Specific wording and examples in README Development section
- Whether to remove or deprecate root `requirements.txt` file (Phase 10 D-06 said default is delete once README/Docker no longer reference it)

</decisions>

<specifics>
## Specific Ideas

- User wants multi-stage Docker build to keep final image small
- User values layer caching for faster rebuilds (copy lockfile early)
- User wants clear separation between operator docs (Deployment) and maintainer docs (Development)
- No PyPI publishing — Docker Hub and GHCR are the only distribution channels
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements

- `.planning/ROADMAP.md` — Phase 12 goal, success criteria, boundary
- `.planning/REQUIREMENTS.md` — DOCK-01, DOC-01, DIST-01 wording
- `.planning/PROJECT.md` — Current Milestone v1.2 goals, Docker-only distribution decision

### Prior phase context

- `.planning/phases/10-uv-python-3-13-lockfile/10-CONTEXT.md` — D-01 (pyproject.toml metadata), D-02 (hatchling backend), D-04 (uv.lock committed)
- `.planning/phases/11-jellyswipe-package-layout/11-CONTEXT.md` — D-10 (Gunicorn entry point `jellyswipe:app`), D-12/D-13 (templates/static under jellyswipe/ with package data)

### Current code state (pre-change)

- `Dockerfile` — Current `pip install -e .` approach (needs uv conversion)
- `pyproject.toml` — Project metadata, dependencies, hatchling build backend, package data for templates/static
- `uv.lock` — Committed lockfile from Phase 10 (read-only for this phase)
- `README.md` — Has Deployment section but no Development section for maintainers
- `.github/workflows/docker-image.yml` — CI builds and pushes to Docker Hub (no PyPI workflow)
- `.github/workflows/release-ghcr.yml` — CI builds and pushes to GHCR on releases (no PyPI workflow)

### Codebase maps

- `.planning/codebase/STACK.md` — Current Python 3.13 base image, Docker build context
- `.planning/codebase/STRUCTURE.md` — Dockerfile location, templates/static structure under jellyswipe/

No external specs or ADRs for this phase — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`pyproject.toml`** — Already configured with `name = "jellyswipe"`, `requires-python = ">=3.13,<3.14"`, hatchling build backend, and package data for templates/static
- **`uv.lock`** — Committed lockfile from Phase 10; contains frozen dependency versions for Python 3.13
- **`.github/workflows/docker-image.yml`** — Existing CI for Docker Hub (no changes needed for PyPI avoidance — already Docker-only)
- **`.github/workflows/release-ghcr.yml`** — Existing CI for GHCR releases (no changes needed for PyPI avoidance)

### Established patterns

- **Multi-stage Docker builds** — Common pattern for Python web apps to keep final image small; uv docs recommend this pattern
- **Layer caching optimization** — Copy dependency files (pyproject.toml, uv.lock) before source code to invalidate dependency layer only when dependencies change
- **Gunicorn entry point** — Already uses `jellyswipe:app` from Phase 11; no changes needed to CMD

### Integration points

- **Docker Hub push** — `.github/workflows/docker-image.yml` builds from Dockerfile; must continue to work after uv changes
- **GHCR release** — `.github/workflows/release-ghcr.yml` builds from Dockerfile; must continue to work after uv changes
- **Operator volume mounts** — `/app/data` must remain writable for SQLite DB; Dockerfile must preserve this path
- **Port exposure** — Port 5005 must remain exposed for existing compose/Unraid deployments

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

### Reviewed Todos (not folded)

No todos matched for Phase 12.

</deferred>

---

*Phase: 12-docker-maintainer-docs*
*Context gathered: 2026-04-25*
