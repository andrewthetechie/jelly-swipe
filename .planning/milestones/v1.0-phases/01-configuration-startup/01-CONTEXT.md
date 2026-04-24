# Phase 1: Configuration & startup - Context

**Gathered:** 2026-04-22  
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver **either/or media provider selection** and **startup + documentation** so that:

- `plex` mode keeps today’s required env contract and behavior.
- `jellyfin` mode starts without any Plex-specific variables present.
- Operators understand variables and the **two instances for both backends** rule (from `PROJECT.md`).

Implementation of the provider abstraction, Jellyfin HTTP client, and UI auth belong to later phases — this phase only names, validates, and documents configuration.

</domain>

<decisions>
## Implementation Decisions

### Provider selection (CFG-01)

- **D-01:** Single env var **`MEDIA_PROVIDER`**, values **`plex`** or **`jellyfin`**, case-insensitive on read; normalize to lowercase internally before branching.
- **D-02:** If **`MEDIA_PROVIDER` is unset or empty**, default to **`plex`** so existing deployments and compose files keep working without changes.

### Required variables per mode (CFG-02)

- **D-03:** Always require **`TMDB_API_KEY`** and **`FLASK_SECRET`** in every mode (unchanged global deps).
- **D-04:** **Plex mode** requires **`PLEX_URL`** and **`PLEX_TOKEN`** (same semantics as today); do not require any `JELLYFIN_*` vars.
- **D-05:** **Jellyfin mode** requires **`JELLYFIN_URL`** (scheme + host + optional port, no trailing slash policy: strip like `PLEX_URL`).
- **D-06:** Jellyfin authentication credentials for **server/library** access are **one of two bundles** (document both in README):
  - **A)** `JELLYFIN_API_KEY` set (non-empty), **or**
  - **B)** both `JELLYFIN_USERNAME` and `JELLYFIN_PASSWORD` set.  
  Validation: if Jellyfin mode and neither bundle is satisfied, fail startup with a single clear error listing missing names. (How the app exchanges password for a token is Phase 3; Phase 1 only validates presence.)
- **D-07:** On validation failure, keep the same **fail-fast at process startup** style as the current `raise RuntimeError(f"Missing env vars: {missing}")` block (no lazy/deferred validation for missing core config).
- **D-10:** In **`jellyfin`** mode, **`PLEX_URL` and `PLEX_TOKEN` must not appear in the required-env list** (operators may omit them entirely). Whether **`plexapi` remains an install-time dependency** until Phase 2 is planner discretion: **prefer** a small lazy-import or conditional import in Phase 1 if it is a short, reviewable change; otherwise explicitly defer import decoupling to Phase 2 while still meeting D-10 for **environment** validation.

### Documentation (CFG-03)

- **D-08:** **`README.md`** is the primary operator reference: table of variables for Plex vs Jellyfin, example minimal `.env` snippets for each mode, and an explicit **“Plex + Jellyfin together = two instances”** note aligned with `PROJECT.md`.
- **D-09:** **`docker-compose.yml`** (or companion env example): add **commented** second env block or short comment pointing to README for Jellyfin-only variables — avoid maintaining two full duplicate service definitions unless the repo already uses compose profiles (it does not); do not introduce scope beyond one compose file + README.

### Claude's Discretion

- Exact error message wording and ordering of missing-var lists.
- Minor README formatting (tables vs lists) as long as both modes are unambiguous.
- Whether to read `MEDIA_PROVIDER` once at module level vs a tiny helper — implementation detail.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning / product

- `.planning/PROJECT.md` — Either-or provider, two-instance rule, out of scope for dual-backend single process.
- `.planning/REQUIREMENTS.md` — CFG-01, CFG-02, CFG-03 acceptance wording.
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria (Jellyfin starts without Plex vars; README/compose expectations).

### Current implementation (to preserve Plex contract)

- `app.py` — Existing `required` list and `RuntimeError` on missing env (lines ~18–21); `PLEX_URL` / `PLEX_TOKEN` usage patterns.
- `docker-compose.yml` — Current env wiring for Plex deployment.

### Research (optional context for later phases; not blocking Phase 1)

- `.planning/research/STACK.md` — Jellyfin auth header notes for Phase 3+.

No separate SPEC for this phase — requirements are in `REQUIREMENTS.md` only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`app.py` top-level env validation** — Extend the existing `required` pattern into provider-conditional lists instead of introducing a new config framework.

### Established patterns

- **Fail at import** — `missing` check runs when `app.py` loads; new logic should stay predictable (no first-request surprise).

### Integration points

- **`app.py` imports** — `from plexapi...` at module import time is the main coupling risk for “start without Plex” **installs**; see decision **D-10** in `<decisions>`.

</code_context>

<specifics>
## Specific Ideas

- Async discuss session: gray areas were resolved using **brownfield-safe defaults** (default `plex`, `MEDIA_PROVIDER` name, dual credential bundles for Jellyfin, README-first docs). Operator may edit `01-CONTEXT.md` before `/gsd-plan-phase 1` if they prefer different env names.

</specifics>

<deferred>
## Deferred Ideas

- Renaming DB column `plex_id` to a neutral name — v2 / OPS in `REQUIREMENTS.md`, not Phase 1.
- Compose **profiles** for side-by-side Plex and Jellyfin stacks — product choice is two instances; optional doc note only.

### Reviewed Todos (not folded)

- None — `todo.match-phase` returned no matches.

</deferred>

---

*Phase: 01-configuration-startup*  
*Context gathered: 2026-04-22*
