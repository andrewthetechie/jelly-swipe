# Requirements: Jelly Swipe — v1.2

**Defined:** 2026-04-24  
**Core value:** Users can run a swipe session backed by either Plex or Jellyfin (one backend per deployment), with library browsing and deck behavior equivalent to the Plex path.

Milestone focus: **uv** + **Python 3.13** packaging, **`jellyswipe/`** layout, **Docker-only** distribution.

## v1.2 Requirements

### Tooling & dependencies (uv)

- [ ] **UV-01**: The repository uses **uv** as the canonical way to declare and lock dependencies (`pyproject.toml` + committed **`uv.lock`**). Root **`requirements.txt`** is not the primary install path for Docker or maintainer docs.
- [ ] **UV-02**: **`requires-python`** and the container base image target **Python 3.13** consistently.
- [ ] **DEP-01**: Direct runtime dependencies are pinned in the lockfile to **newest versions compatible** with Python 3.13 and the existing application; `uv sync` / image build succeeds and the app starts with required env vars.

### Package layout

- [ ] **PKG-01**: Server code that today lives in repo-root **`app.py`** and **`media_provider/`** is organized under an importable **`jellyswipe/`** package (no duplicate competing top-level app packages).
- [ ] **PKG-02**: **Gunicorn** (Docker `CMD` and documented production path) imports the Flask application from the **`jellyswipe`** package (stable module:attribute, e.g. `jellyswipe.web:app` — exact name chosen at implementation).

### Docker & documentation

- [ ] **DOCK-01**: **`Dockerfile`** installs Python dependencies using **uv** (frozen lockfile in image) and runs the WSGI app from the **`jellyswipe`** package; exposed port and **`/app/data`** (or equivalent) behavior remain suitable for existing compose/Unraid operator flows.
- [ ] **DOC-01**: **`README.md`** explains how maintainers use **uv** (`uv sync`, `uv run`, …) instead of `pip install -r requirements.txt`.

### Distribution scope

- [ ] **DIST-01**: The project does **not** add a PyPI publishing workflow or position **`jellyswipe`** as an installable product from PyPI; distribution remains **Docker Hub / GHCR** and source checkout only.

## Future requirements

_Deferred past v1.2 (see `.planning/PROJECT.md` Active candidates)._

- **ARC-02** — Plex regression matrix completion from archived Phase 2 verification.
- **OPS-01 / PRD-01** — Neutral DB columns and multi-library selection.

## Out of scope

| Item | Reason |
|------|--------|
| **PyPI package** | Explicit v1.2 decision: Docker (and source) only. |
| **Changing product behavior** | v1.2 is packaging/tooling; Plex/Jellyfin behavior stays equivalent unless a dependency upgrade forces a minimal fix. |
| **Both Plex and Jellyfin in one process** | Existing product decision. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UV-01 | Phase 10 | Pending |
| UV-02 | Phase 10 | Pending |
| DEP-01 | Phase 10 | Pending |
| PKG-01 | Phase 11 | Pending |
| PKG-02 | Phase 11 | Pending |
| DOCK-01 | Phase 12 | Pending |
| DOC-01 | Phase 12 | Pending |
| DIST-01 | Phase 12 | Pending |

**Coverage:** v1.2 requirements: **8** total · Mapped: **8** · Unmapped: **0**

---
*Requirements defined: 2026-04-24 — milestone v1.2*
