# Phase 12: Docker & maintainer docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-25
**Phase:** 12-docker-maintainer-docs
**Mode:** discuss
**Areas discussed:** 2

## Areas Discussed

### 1. Dockerfile uv integration

| Question | User Selection | Options Presented |
|----------|----------------|-------------------|
| Which areas to discuss? | Dockerfile uv integration, README development docs | Dockerfile uv integration, README development docs, PyPI story avoidance, Discuss all areas |
| How should uv be installed in the Dockerfile? | Other: "Use the builder pattern to install uv using pip in a builder layer and then package jellyswipe into a wheel. Then in the final image, copy the wheel over, install it, then delete the wheel." | pip install uv, then uv sync; uv installer script; Pre-built uv image |
| In the builder stage, how should dependencies be handled? | uv sync from lockfile | uv sync from lockfile; uv pip install -e .; Build wheel with deps |
| How should Docker layers be structured for caching? | Copy lockfile early | Copy lockfile early; Copy all, single sync; You decide |

**Decisions captured:**
- D-01: Multi-stage build with builder pattern (install uv via pip, package jellyswipe into wheel, final stage copies/installs/deletes wheel)
- D-02: Use `uv sync` from uv.lock for dependencies in builder stage
- D-03: Copy pyproject.toml and uv.lock early, run uv sync, then copy source and run uv sync again (layer caching optimization)
- D-04: Keep existing Gunicorn CMD from Phase 11
- D-05: Preserve port 5005 and /app/data behavior

### 2. README development documentation

| Question | User Selection | Options Presented |
|----------|----------------|-------------------|
| Which uv commands should be documented in the README? | Sync, run, dev server, add | Sync, run, dev server, add; Sync and run only; Full uv CLI reference |
| Where should the uv development documentation go in the README? | New Development section | New Development section; Add to Deployment; New CONTRIBUTING.md |
| Which gray areas remain unclear? | I'm ready for context | I'm ready for context; More questions |

**Decisions captured:**
- D-06: Add new "Development" section to README.md after "Deployment"
- D-07: Document uv sync, uv run python -m jellyswipe, uv run gunicorn jellyswipe:app, uv add, uv lock --upgrade
- D-08: Include Python 3.13 requirement note

### 3. PyPI story avoidance

**Status:** Not discussed (user did not select this area)

**Pre-existing state captured:**
- D-09: No PyPI publishing workflow to be added (existing workflows are Docker-only)
- D-10: No documentation implying pip install jellyswipe from PyPI

## Corrections Made

No corrections — all questions answered directly.

## Auto-Resolved

Not applicable (interactive mode, not --auto).

## External Research

Not applicable (no external research needed for this phase).
