# Phase 10: uv & Python 3.13 lockfile - Context

**Gathered:** 2026-04-24  
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce **`pyproject.toml`** and a committed **`uv.lock`** so dependency management is **uv-first** on **Python 3.13**, with direct dependencies at **newest versions compatible** with the current app (UV-01, UV-02, DEP-01). Retire root **`requirements.txt`** as the canonical install source.

**Explicitly out of this phase:** Moving `app.py` / `media_provider` under `jellyswipe/` (Phase 11), Dockerfile/README uv instructions (Phase 12), PyPI narrative (Phase 12 / DIST-01).

**Shim allowance (per ROADMAP success criteria):** A **temporary** import/smoke path is acceptable if needed to validate the lockfile before Phase 11 lands the real package layout; any shim must not expand scope into full package relocation.

</domain>

<decisions>
## Implementation Decisions

### Project metadata & Python version

- **D-01:** Root **`pyproject.toml`** uses PEP 621 **`[project]`** with `name = "jellyswipe"` (matches v1.2 package naming), a **`version`** aligned with the product line (e.g. current release tag or `0.0.0` placeholder — planner picks one convention and documents it), and **`requires-python = ">=3.13,<3.14"`** (UV-02: single minor line, no 3.12 support in metadata for this milestone).
- **D-02:** **Build backend:** use **`hatchling`** as `[build-system]` (uv ecosystem default). Package discovery / `packages = ["jellyswipe"]` wiring follows whatever exists in the tree at implementation time: if Phase 10 runs **before** `jellyswipe/` exists, use uv’s supported pattern for a **dependency-only** or **non-installable** project (`uv` docs / `package = false` or equivalent) so **`uv lock`** and **`uv sync`** succeed without faking a full package tree; once `jellyswipe/` exists (Phase 11), hatch config must include it.

### Dependencies & lockfile

- **D-03:** **Runtime dependencies** for Phase 10 are the current set from **`requirements.txt`**: `flask`, `plexapi`, `werkzeug`, `requests`, `python-dotenv`, `gunicorn` — migrated verbatim as direct **`[project.dependencies]`** entries, then **upgraded** to newest **3.13-compatible** releases via **`uv lock --upgrade`** (or `uv add` at latest), followed by **import/`py_compile` smoke** on `app.py` + `media_provider/*.py` (DEP-01).
- **D-04:** **Commit `uv.lock`** to git; CI and Docker (Phase 12) will consume the frozen lock; Phase 10 deliverable includes the lockfile even if Dockerfile still uses pip until Phase 12.
- **D-05:** **No new dev/test dependency groups** in Phase 10 unless already required by repo (there is **no** `pytest`/`ruff` in-tree today); optional **`[dependency-groups]`** for dev tools is **Claude’s discretion** for a later milestone, not Phase 10.

### requirements.txt & install UX

- **D-06:** After **`uv sync`** is documented internally and smoke-validated, **remove `requirements.txt`** or replace with a **generated export only** if absolutely needed for an external consumer — **default decision: delete** root `requirements.txt` once README/Docker no longer reference it (full removal may land in Phase 12 with DOCK/DOC; Phase 10 must at minimum **stop treating it as canonical** per UV-01).

### Verification

- **D-07:** Phase 10 **exit checks:** `uv sync` (Python 3.13), **`uv run python -m py_compile app.py`** and **`media_provider/*.py`** (or `uv run` equivalent), and **`uv lock`** reproducible from clean checkout.

### Claude's Discretion

- Exact **`version`** field in `pyproject.toml`, hatch **`[tool.hatch.build]`** details until `jellyswipe/` exists, and whether to add a **one-file stub** under `jellyswipe/` in Phase 10 solely to satisfy packaging tools (prefer **avoid** if uv allows lock without installable package).

</decisions>

<specifics>
## Specific Ideas

- Milestone intent: **Docker-only** distribution; Phase 10 does not add PyPI metadata beyond what a normal `pyproject.toml` carries.
- Operator-facing install stays on **Docker** until Phase 12 updates the Dockerfile.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone & phase scope

- `.planning/ROADMAP.md` — Phase 10 goal, success criteria, boundary vs Phases 11–12  
- `.planning/REQUIREMENTS.md` — UV-01, UV-02, DEP-01 wording  
- `.planning/PROJECT.md` — Current Milestone v1.2 goals and constraints  

### Current runtime & packaging (pre-change)

- `requirements.txt` — Source list of dependencies to migrate  
- `Dockerfile` — Still `pip` + `requirements.txt` until Phase 12 (read-only context for Phase 10)  
- `app.py` — Import-time env validation; smoke target for `py_compile`  
- `media_provider/` — Provider modules; smoke target for `py_compile`  

### Architecture background (optional)

- `.planning/codebase/STACK.md` — Prior note on pip / Python version (may be stale vs 3.13; prefer `Dockerfile` + this CONTEXT)  
- `.planning/codebase/STRUCTURE.md` — Monolith + `media_provider` layout before Phase 11  

No separate SPEC.md for Phase 10.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`requirements.txt`** — Definitive dependency names for migration into `pyproject.toml`.

### Established patterns

- **Monolithic `app.py`** + top-level **`media_provider`** package; imports like `from media_provider import get_provider` — unchanged in Phase 10; Phase 11 will relocate.

### Integration points

- **`uv lock` / `uv sync`** must resolve environments that can still run **`gunicorn ... app:app`** (current Dockerfile) until Phase 12 switches the entrypoint.

</code_context>

<deferred>
## Deferred Ideas

- **`jellyswipe/`** package layout, Gunicorn module path, Flask template paths — **Phase 11** (PKG-01, PKG-02).  
- **Dockerfile uv**, **README uv**, **DIST-01** copy — **Phase 12**.  
- **ARC-02 / OPS-01** — remain future milestone candidates per `PROJECT.md`.

### Reviewed Todos (not folded)

- `gsd-sdk query todo.match-phase "10"` returned no usable matches in this environment — nothing folded from todo backlog.

</deferred>

---

*Phase: 10-uv-python-3-13-lockfile*  
*Context gathered: 2026-04-24*
