# Phase 2 research: Media provider abstraction

**Research date:** 2026-04-22  
**Repo:** kino-swipe (`/Users/andrew/Documents/code/kino-swipe`)  
**Question answered:** *What do I need to know to PLAN this phase well?*

---

## Summary for the planner

Phase 2 is a **structural refactor** of an existing Flask monolith: almost all Plex library I/O today lives in `app.py` as free functions (`get_plex`, `reset_plex`, `get_plex_genres`, `fetch_plex_movies`) plus inline route logic for `/proxy`, `/plex/server-info`, trailer/cast TMDB prep, and genre/movie routes. The plan should specify a **`media_provider/`** package with an **`abc.ABC`** contract, a **`PlexLibraryProvider`**, and a **process-wide singleton** factory (`get_provider()` + `reset()`), migrating call sites in **one coherent change set** while **leaving Plex.tv pin auth and `/watchlist/add` in `app.py`** (they remain Plex-specific product surfaces, not part of the library provider contract per locked decisions).

Jellyfin **does not gain working library behavior** in this phase: startup may already accept Jellyfin env (Phase 1); library paths must **fail fast** with a clear message until later phases. **ARC-03** is satisfied by **architecture and file placement** (no scattered Jellyfin HTTP in random helpers)—Phase 2 explicitly **does not** add `jellyfin.py`; the dedicated Jellyfin client module is a **Phase 3 deliverable**, named and imported from the factory when that phase lands.

**No new pip dependencies** are required: `abc` is stdlib; `plexapi` stays where it is today (lazy import inside the Plex provider is consistent with current `get_plex()`).

---

## Requirements mapping (ARC-01 — ARC-03)

### ARC-01 — Stable provider API

**Plan must enumerate** every library-facing capability that routes need today and bind each to one or more abstract methods (exact names are discretionary):

| Capability | Current location (indicative) | Notes for interface |
|------------|-------------------------------|----------------------|
| Genre list (with Sci-Fi label normalization) | `get_plex_genres()` | Cache moves onto provider instance (not `app.py` global). |
| Movie deck JSON (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`) | `fetch_plex_movies(genre_name)` | Preserve shuffle rules, “Recently Added” sort, Sci-Fi ↔ Science Fiction mapping. |
| Resolve item by provider id for TMDB (title/year) | `get_plex()` + `fetchItem` in `get_trailer`, `get_cast`, `/watchlist/add` | Same underlying Plex operation; routes for trailer/cast (and optionally watchlist item fetch) should go through the provider for **one** code path to “load movie metadata by id.” |
| Server stable id + display name | `/plex/server-info` | Keep response shape `{ machineIdentifier, name }` and route path `/plex/server-info` for Plex mode (no neutral rename this phase). |
| Poster / image behavior behind `/proxy` rules | `/proxy` | Today: `MEDIA_PROVIDER == "plex"`, path must start with `/library/metadata/`, upstream `GET` with admin token. Abstraction should **own** “validated image fetch for card thumbs” so Phase 4 can swap Jellyfin logic without reopening every route. |

Callable-from-routes means the factory returns a concrete implementation selected by `MEDIA_PROVIDER` (Plex only fully implemented in Phase 2).

### ARC-02 — Plex parity

**Definition of done** is behavioral equivalence with **pre-refactor** Plex mode:

- Same JSON shapes for `/genres`, `/movies`, room create + genre refetch, `/plex/server-info`, `/get-trailer/<id>`, `/cast/<id>`, and `/proxy` success/error semantics where unchanged.
- Same retry pattern: attempt → on failure `reset()` (today `reset_plex()`) → retry for `fetchItem`, server info, and initial section access in deck fetch.
- Watchlist and Plex.tv auth routes **unchanged in product behavior** (they may still import `plexapi` for `MyPlexAccount` / user token flows; they must not be forced behind the library ABC).

**Planning artifact:** a short **parity checklist** in PLAN.md (bullet list of endpoints + one manual scenario each) beats prose-only “match before.”

### ARC-03 — Jellyfin in a dedicated module (not scattered)

In Phase 2:

- **Do not** add a placeholder `jellyfin` implementation file.
- **Do** structure the codebase so Jellyfin HTTP/auth will live in **one future module** (e.g. `media_provider/jellyfin_client.py` or `jellyfin_provider.py` in Phase 3—exact name is a plan detail) and be wired **only** through the factory + concrete provider class.
- **`get_provider()`** for `MEDIA_PROVIDER=jellyfin` should raise a **single, explicit** error at call time (or app startup policy already defined in Phase 1—align with roadmap) rather than failing halfway through a route with `ImportError`.

The planner should reference **REQUIREMENTS.md** traceability: ARC-03 is marked Phase 2 **Pending** until this structural guarantee exists in code review.

---

## Current code reality (`app.py`)

All production Plex library usage today is **centralized in one file** (~500 lines). Grep confirms **`get_plex` / `reset_plex` / `fetch_plex_movies` / `get_plex_genres`** appear only under `app.py` (plus planning docs)—migration surface area is bounded.

**Routes / helpers to touch in the refactor pass:**

- `get_plex`, `reset_plex`, `_plex_instance`, `_genre_cache`, `get_plex_genres`, `fetch_plex_movies`
- `create_room`, `get_movies`, `get_genres` (call `fetch_plex_movies` / `get_plex_genres`)
- `get_trailer`, `get_cast` (Plex item → TMDB; keep TMDB in routes or small helpers—provider supplies title/year or item resolution only)
- `get_server_info` (`/plex/server-info`)
- `/proxy` (Plex upstream streaming)
- `/watchlist/add` — uses `get_plex` + `fetchItem` + `MyPlexAccount`; **keep route-level** per D-03; plan whether it calls a **narrow** provider method for `fetchItem` only (recommended to avoid duplicating retry/reset) *without* expanding the ABC to “watchlist.”

**Explicitly out of Phase 2 provider ABC (per context):**

- `/auth/plex-url`, `/auth/check-returned-pin`
- `/watchlist/add` as a *feature* (not a method named “watchlist” on the provider)

---

## Design constraints the plan must respect

1. **Flask monolith** — no new framework; register routes as today; provider is imported from `media_provider`.
2. **Exceptions** — provider/library code raises; routes keep `try`/`except` → `jsonify({'error': str(e)}), 500` (or existing status codes).
3. **Singleton + reset** — mirror `_plex_instance` / `reset_plex()`; any code path that today calls `reset_plex()` after errors should call `get_provider().reset()` (or module-level `reset_provider()`—planner picks one style and uses it consistently).
4. **Lazy `plexapi` import** — keep import inside Plex construction (avoids import-time coupling; matches current `get_plex()` pattern).
5. **Environment** — `PLEX_URL`, `ADMIN_TOKEN` (or equivalent names already in `app.py`) are read at module level today; the provider can receive them via factory/build args to keep testing injectable without global env mutation where possible.
6. **No new pip deps** unless a planner identifies an unavoidable gap (none identified in this research).

---

## Suggested PLAN.md structure (non-normative)

1. **Interface sketch** — list abstract methods mapping to A–E in `02-CONTEXT.md` (D-02).
2. **File list** — `media_provider/__init__.py`, `base.py` (ABC), `plex_library.py` (name flexible), `factory.py` (`get_provider`, `reset`).
3. **Migration order** — introduce factory + ABC + Plex impl → switch routes one group at a time (genres + movies + room create first; trailer/cast/server-info/proxy second) *or* true single diff if review bandwidth allows (D-09).
4. **Jellyfin branch** — factory behavior and user-visible error strings.
5. **Verification** — link to checklist; see **Validation Architecture** below.

---

## Risks and planning traps

- **Scope creep:** folding Plex.tv or watchlist “convenience” into the ABC—explicitly forbidden for Phase 2 scope; document boundary in PLAN.
- **Proxy duplication:** if `/proxy` stays partially in `app.py`, Jellyfin later will miss parity—plan should assign **one** owner for path validation + upstream fetch.
- **Watchlist vs provider:** if watchlist keeps calling raw `get_plex()`, the old global path might survive refactor incomplete—grep plan should catch **any** remaining `get_plex(` outside the provider module after migration.
- **Genre cache staleness:** today cache survives `reset_plex()`; decide whether `reset()` clears genre cache (likely yes if connection identity changes—planner documents one rule).

---

## Validation Architecture

This section defines how to **verify ARC-01, ARC-02, and ARC-03** during Phase 2 execution—not as a full CI overhaul, but as **credible evidence** the abstraction landed and Plex parity held.

### ARC-01 (library flows through provider)

- **Manual Plex smoke:** Exercise every route that previously called `get_plex` / `fetch_plex_movies` / `get_plex_genres` or encoded Plex-only proxy behavior: create room, list genres, switch genre via `/movies`, open cards (thumbs via `/proxy`), `/plex/server-info`, trailer and cast for a known `movie_id`. Confirm responses match pre-change snapshots (shape and key fields).
- **Grep-based invariant:** After implementation, `rg 'get_plex\\(|fetch_plex_movies|get_plex_genres'` should return **no matches in `app.py`** (or only in comments), and **`get_provider(`** (or the chosen factory name) should appear at each former call site. A second pass: `rg 'plex\\.library|plexapi'` in `app.py` should be limited to **explicitly out-of-scope** routes (`/watchlist/add`, pin auth) plus imports if any remain—document the expected allowlist in PLAN.
- **Optional pytest with mocks:** The codebase today has little or no test harness enforced in CI; optional tests can mock a **narrow provider protocol** (or fake concrete class) and assert routes call `get_provider()` and propagate JSON errors. Mock at the **`get_provider` binding** (patch in route tests) to avoid pulling `plexapi`. This is **optional** for Phase 2 to ship quality; it seeds a pattern for later waves.

### ARC-02 (Plex behavioral match)

- **Manual Plex smoke** is the **source of truth** for parity in this milestone: same deck field set, genre list including “Recently Added” and Sci-Fi labeling, `/proxy` 403 on bad paths and 503 when not in Plex mode (if unchanged from Phase 1), TMDB trailer/cast success/failure behavior.
- **Sampling strategy:** Pick **two** genres (one normal, one “Sci-Fi”), **Recently Added**, and **All**; verify shuffle vs deterministic order matches current semantics. Pick **two** movies (one with TMDB hit, one edge case) for trailer/cast.
- **Regression guard (lightweight):** If optional pytest exists, golden-fixture JSON comparison for `fetch_*_movies` output from a **stub provider** (fixed list) can lock object shape without needing a real Plex server in CI.

### ARC-03 (Jellyfin not scattered; dedicated module later)

- **Structural review:** Confirm **no** new Jellyfin HTTP client code in `app.py` helpers, `media_provider/plex_*.py`, or random utilities—only a **factory branch** that fails fast (or defers to Phase 3 file once written).
- **Grep checks:** `rg -i jellyfin` across `media_provider/` and `app.py` should only hit config/factory messaging until Phase 3 adds the dedicated module.
- **Manual:** Start process with `MEDIA_PROVIDER=jellyfin` and required Jellyfin env from Phase 1; confirm **clear fail-fast** behavior (startup or first library call—align with Phase 1 locked behavior) and **no** partial library responses.

### Sampling strategy (cross-requirement)

Use a **small matrix** rather than exhaustive testing: **3** genre modes × **2** movies × **1** proxy negative path × **1** server-info call × **jellyfin** fail-fast path. Record results in phase verification notes.

### Future automation (Wave 0)

A **full automated suite** (CI-blocked pytest with Dockerized Plex or recorded HTTP fixtures, plus frontend e2e) is **out of scope** for this research’s minimum bar; treat it as **Wave 0** for a later milestone: introduce test containers, stable test library IDs, and contract tests for `get_provider()` once Jellyfin exists (Phase 3–4). Phase 2 should **not** block on that infrastructure.

---

## References

- `.planning/phases/02-media-provider-abstraction/02-CONTEXT.md` — locked decisions D-01–D-11.
- `.planning/REQUIREMENTS.md` — ARC-01–ARC-03.
- `.planning/STATE.md` — next step `/gsd-plan-phase 2`.
- `app.py` — current singleton, cache, routes, `/proxy`.
- `.planning/codebase/ARCHITECTURE.md`, `INTEGRATIONS.md` — integration map and caching note.

---

*Phase: 02-media-provider-abstraction · Research artifact for PLAN.md*
