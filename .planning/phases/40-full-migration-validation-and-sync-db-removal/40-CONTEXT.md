# Phase 40: Full Migration Validation and Sync DB Removal - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Close v2.1 by proving Alembic migration parity (empty DB → head, idempotent upgrade on an already-current DB), keeping the full automated test suite green, and removing obsolete synchronous / ad hoc application database access (`sqlite3`, `get_db_closing`, table-creating `init_db()`, SQLModel) from the **application package** while preserving an auditable planning record of requirement coverage and any intentionally deferred work.

</domain>

<decisions>
## Implementation Decisions

### Migration parity tests (VAL-02)
- **D-01:** VAL-02 tests live where the planner sees least duplication with existing `tests/conftest.py` Alembic/bootstrap fixtures (no mandate for a brand-new top-level module vs extending an existing migration-focused test file).
- **D-02:** Assert already-at-head idempotency by **invoking the Alembic CLI via subprocess** so the test mirrors operator-style upgrades (not only a single programmatic double-run unless the planner adds both).
- **D-03:** Use an **isolated temp-DB fixture** for migration parity tests (not necessarily the same surface as all route tests) for clarity and speed.
- **D-04:** Minimum empty-database proof: **fresh file DB → `upgrade head` → table presence checks** (planner may strengthen with version row or smoke queries).

### VAL-04 application-layer boundary
- **D-05:** Ban on `sqlite3` for **runtime application code** applies to `jellyswipe/` only; tests, one-off scripts, and Alembic toolchain may still import `sqlite3` when needed.
- **D-06:** **`alembic/`** (revision scripts, `env.py`) may use low-level SQLite hooks required by the migration toolchain; VAL-04 targets **application runtime**, not migration offline SQL.
- **D-07:** Remove any **table-creating** `init_db()` / ad hoc DDL paths from the app; a non-DDL stub or transitional import is acceptable if the planner needs a thin compatibility seam during the final cutover.
- **D-08:** **SQLModel:** zero imports in **`jellyswipe/`** only; dev tooling elsewhere is out of scope unless it ships in the runtime image.

### Legacy removal sequencing
- **D-09:** Phase 40 implementation **starts only after Phase 39 is merged** (no overlapping stubbed removal).
- **D-10:** **`jellyswipe/db.py`:** planner chooses between full deletion vs a **small residue module** (constants/helpers only) depending on what remains after Phases 36–39.
- **D-11:** CI / pre-merge gate before calling Phase 40 done: planner picks the **minimal combination** that satisfies VAL-03 and VAL-04 (full `pytest` + a practical grep/script strategy).
- **D-12:** **`run_sync()` / `BEGIN IMMEDIATE` bridge:** planner decides retain vs eliminate based on post–Phase-39 necessity and behavioral parity (not locked here).

### Planning verification record
- **D-13:** The **canonical planning verification artifact** for this phase is **`40-VALIDATION.md`** in this directory (same family as Phase 39’s validation contract): a requirement → evidence matrix for **ADB-03, VAL-02, VAL-03, VAL-04**, plus sampling/sign-off aligned with Nyquist settings in `.planning/config.json`.
- **D-14:** **Intentionally deferred** persistence or architecture items (including anything discovered during final removal) must appear both in **`40-VALIDATION.md` (Deferred / out-of-scope subsection)** and in this file’s `<deferred>` block so milestone closure does not silently drop scope.
- **D-15:** **`REQUIREMENTS.md` checkbox updates** happen when verification is proven (typically at phase close); the validation doc is the working paper that feeds that update—do not rely on CONTEXT alone for sign-off rows.
- **D-16:** Traceability back to `.planning/ROADMAP.md` § Phase 40 success criteria is part of **`40-VALIDATION.md`** sign-off, not optional narrative.

### Claude's Discretion
- **D-01, D-10, D-11, D-12:** User chose “planner decides” variants in the resumed checkpoint—researcher/planner should pick concrete file names, fixtures, and CI hooks within these rails.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/PROJECT.md` — v2.1 milestone intent and persistence-migration completion criteria
- `.planning/REQUIREMENTS.md` — **ADB-03**, **VAL-02**, **VAL-03**, **VAL-04** (Phase 40)
- `.planning/ROADMAP.md` — § Phase 40 goal, dependency on Phase 39, success criteria (migration tests, suite green, source scan, planning verification)
- `.planning/STATE.md` — current milestone pointer

### Prior phase decisions (persistence migration line)
- `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md` — schema + Alembic baseline
- `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md` — async runtime and UoW
- `.planning/phases/38-auth-persistence-conversion/38-CONTEXT.md` — repository pattern on auth domain
- `.planning/phases/39-room-swipe-match-and-sse-persistence-conversion/39-CONTEXT.md` — room/swipe/match/SSE conversion decisions and parity tests baseline
- `.planning/phases/39-room-swipe-match-and-sse-persistence-conversion/39-VALIDATION.md` — pattern for phase validation / Nyquist-style tables (mirror for Phase 40)

### Application and toolchain (integration / removal targets)
- `jellyswipe/db.py` — legacy sync SQLite entry points targeted for removal or collapse (`sqlite3`, `get_db_closing`, related helpers as of Phase 39 close)
- `jellyswipe/db_uow.py` — async UoW and any remaining `run_sync()` / transactional bridge (per D-12 discretion)
- `jellyswipe/dependencies.py` — request-scoped DB dependencies
- `alembic/env.py` — Alembic runtime (exempt from app-layer sqlite ban per D-06)
- `alembic/versions/0001_phase36_baseline.py` — baseline revision reference for migration parity tests

### Tests
- `tests/conftest.py` — fixtures, temp DB, and Alembic alignment for suite-wide VAL-03
- `pytest` invocation via project config (e.g. `pyproject.toml` `[tool.pytest.ini_options]`) — full suite gate for VAL-03

### External specs
- None beyond planning docs and repository source above unless the planner attaches an ADR in a later artifact.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 39 validation template:** `39-VALIDATION.md` shows the expected `40-VALIDATION.md` shape (matrix, Nyquist frontmatter, sign-off)—reuse structure, rewrite rows for ADB-03 / VAL-02 / VAL-03 / VAL-04.
- **`tests/conftest.py`:** Primary hook for sharing or isolating DB bootstrap for migration tests (per checkpoint D-03).

### Established Patterns
- **Application vs migration boundary:** Runtime FastAPI code uses async SQLAlchemy; Alembic remains the only supported schema authoring path—Phase 40 proves and enforces that split (D-05, D-06).
- **`jellyswipe/db.py`:** Still contains legacy `sqlite3` usage as of this context gather—listed as explicit removal/integration target, not hypothetical.

### Integration points
- Final deletion or shrink of **`jellyswipe/db.py`** ripples through any remaining callers of **`get_db_closing()`**; planner must reconcile with routers already on async repositories from Phase 39.
- CI must enforce **VAL-04** scans on **`jellyswipe/`** only to avoid false positives from `tests/` or `alembic/` (per D-05).

**Note:** `.planning/codebase/TESTING.md` and `STACK.md` are stale vs the current FastAPI/pytest layout; prefer live `tests/` and Phase 39 context for conventions.

</code_context>

<specifics>
## Specific Ideas

- Treat subprocess Alembic for idempotency (D-02) as the “ops-faithful” path so CI and local dev match how upgrades are run in containers.
- Keep validation honest: if `run_sync()` survives Phase 40, document **why** in `40-VALIDATION.md` under deferred or technical debt with a follow-up pointer—not as silent drift.

</specifics>

<deferred>
## Deferred Ideas

None captured during Phase 40 discussion—all items belonged in milestone closure scope.

### Reviewed Todos (not folded)
None (`todo.match-phase 40` returned no matches).

</deferred>

---

*Phase: 40-full-migration-validation-and-sync-db-removal*
*Context gathered: 2026-05-07 (resumed from `40-DISCUSS-CHECKPOINT.json`)*
