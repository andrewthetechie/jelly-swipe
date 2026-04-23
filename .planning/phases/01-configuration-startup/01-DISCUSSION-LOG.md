# Phase 1: Configuration & startup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.  
> Decisions are captured in `01-CONTEXT.md`.

**Date:** 2026-04-22  
**Phase:** 1 — Configuration & startup  
**Areas discussed:** Provider env & default, Required vars per mode, Startup failure behavior, Documentation layout, Import/dependency coupling (D-10)

---

## Provider env name and default

| Option | Description | Selected |
|--------|-------------|----------|
| `MEDIA_PROVIDER` (`plex` / `jellyfin`) | Single flag, common naming | ✓ |
| `KINOSWIPE_MEDIA_BACKEND` | More prefixed, longer |  |
| Require explicit always | No default; breaks existing deploys |  |

**User's choice:** Recommended default applied (async discuss): `MEDIA_PROVIDER`, default **`plex`** when unset for backward compatibility.

**Notes:** Normalize case-insensitive input to lowercase.

---

## Jellyfin credential shape (validation only in Phase 1)

| Option | Description | Selected |
|--------|-------------|----------|
| API key **or** username+password bundles | Matches common Jellyfin deployments | ✓ |
| API key only | Simpler validation, excludes password-only admins |  |
| Defer all Jellyfin env names to Phase 3 | Less in Phase 1; weaker CFG-02 clarity |  |

**User's choice:** Recommended default: validate **`JELLYFIN_URL`** plus either **`JELLYFIN_API_KEY`** or **`JELLYFIN_USERNAME`+`JELLYFIN_PASSWORD`**; token exchange implementation deferred to Phase 3.

---

## Startup failure and docs

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast at startup (current style) | Consistent with existing `RuntimeError` | ✓ |
| README-first + compose comments | Minimal compose churn | ✓ |
| Lazy validation on first /movies | Avoids startup errors |  |

**User's choice:** Recommended defaults as marked.

---

## Plex import / optional dependency

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 1: env-only guarantee; Phase 2: lazy import | Split if import coupling is non-trivial | ✓ |
| Phase 1 must remove plexapi import for jellyfin | Stricter; may blur phase boundary |  |

**User's choice:** **D-10** — Phase 1 guarantees missing **Plex env vars** in Jellyfin mode; lazy import / dependency split is **planner discretion** (prefer in Phase 1 if small).

---

## Claude's Discretion

- Exact validation error strings; README layout; whether lazy Plex import lands in Phase 1 or 2 within D-10 guidance.

## Deferred Ideas

- Compose profiles for dual stack — noted in CONTEXT deferred (two-instance product rule).
