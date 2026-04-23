# Phase 2: Media provider abstraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.  
> Decisions are captured in `02-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-22  
**Phase:** 2 — Media provider abstraction  
**Areas discussed:** Provider interface shape, Module layout, Singleton vs per-request, Refactor sequencing  
**Resolution:** User replied **`defaults`** — all sub-questions resolved using the **recommended** option from the orchestrator’s batch (session 2026-04-22).

---

## Provider interface shape

| Option | Description | Selected |
|--------|-------------|----------|
| Protocol | Structural typing, no inheritance | |
| ABC + PlexLibraryProvider | Formal contract + concrete Plex class | ✓ |
| Duck typing only | No formal interface | |

**Q2 (surface):** A–E all in scope — genres, deck JSON, item resolve for TMDB, server info, image/proxy behavior.

| Option | Description | Selected |
|--------|-------------|----------|
| Watchlist/pin outside provider | Library provider = library + TMDB chain + proxy + server-info | ✓ |
| Same interface | Include Plex.tv + watchlist now | |

| Option | Description | Selected |
|--------|-------------|----------|
| Exceptions to routes | Keep try/except + JSON errors | ✓ |
| Result tuples | `(ok, payload)` everywhere | |

**User's choice:** Recommended set (`defaults`).  
**Notes:** Aligns with ARC-01 wording and roadmap success criteria listing genres, deck, item for TMDB, server info, poster fetch through the interface.

---

## Module layout

| Option | Description | Selected |
|--------|-------------|----------|
| `media_provider/` package | `__init__.py`, split modules, factory | ✓ |
| Two root modules | e.g. `media_provider_base.py` + `plex_library.py` | |
| Single `media_provider.py` | All in one file | |

| Option | Description | Selected |
|--------|-------------|----------|
| No Jellyfin file in Phase 2 | Jellyfin module with Phase 3 | ✓ |
| Stub `jellyfin.py` now | Placeholder / raises | |

**User's choice:** Recommended (`defaults`).

---

## Singleton vs per-request

| Option | Description | Selected |
|--------|-------------|----------|
| Process singleton + `reset()` | Like `_plex_instance` + `reset_plex()` | ✓ |
| Per-request instance | New provider each HTTP request | |

| Option | Description | Selected |
|--------|-------------|----------|
| Cache on provider | Genre cache owned by provider / singleton | ✓ |
| Module global in `app.py` | Keep `_genre_cache` in app during transition | |

**User's choice:** Recommended (`defaults`).

---

## Refactor sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| One mechanical pass | `get_provider()` + move Plex in one coherent PR | ✓ |
| Facade first | Shims in `app.py`, second pass cleanup | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `/plex/server-info` | Same path and JSON keys | ✓ |
| Rename to neutral path | Broader client change | |

**User's choice:** Recommended (`defaults`).

---

## Claude's Discretion

- Exact method names on the ABC, ordering of migration, docstring/error wording (see `02-CONTEXT.md`).

## Deferred Ideas

- Neutral server-info URL — deferred (keep `/plex/server-info` for Phase 2).
- Optional facade-first split — deferred in favor of one pass.
- Watchlist/pin inside provider — deferred per scope.
