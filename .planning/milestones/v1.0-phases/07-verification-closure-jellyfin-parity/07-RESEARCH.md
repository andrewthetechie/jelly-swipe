# Phase 7 — Technical research

**Phase:** 07 — Verification closure: Jellyfin parity  
**Question:** What do we need to know to plan durable verification artifacts for Phases 3–5?

## Findings

### Artifact topology (locked in `07-CONTEXT.md`)

- Mirror Phase 6: phase-native `03-VERIFICATION.md`, `04-VERIFICATION.md`, `05-VERIFICATION.md` beside their implementation phases; `07-VERIFICATION.md` in this directory as an index plus E2E narrative and closure snapshot.

### Runtime evidence bar

- Same as Phase 6: use **Flask `test_client()`** or a short-lived local Flask process with `env -i` + explicit env vars so results are reproducible without loading operator `.env` files unexpectedly.
- When **no Jellyfin** process listens on `JELLYFIN_URL`, many routes still prove **routing + error shaping** (e.g. `/proxy` **403** on disallowed path without upstream call; **500** JSON on `/plex/server-info` with connection refused after auth probe). Full **PASS** on deck/trailer/cast/proxy bytes requires a healthy Jellyfin — record **PARTIAL/FAIL (upstream)** like `02-VERIFICATION.md` does for Plex.

### Requirement → surface map

| Requirement | Primary surfaces |
|-------------|------------------|
| JAUTH-01 | `app.py` startup env validation; `JellyfinLibraryProvider._login_from_env` |
| JAUTH-02 | `ensure_authenticated`, `_verify_items`, `reset()` in `jellyfin_library.py`; factory `get_provider()` |
| JAUTH-03 | JSON error payloads from `app.py` routes; `RuntimeError` messages from provider (must not echo API key or access token strings) |
| JLIB-01–05 | `fetch_deck`, `list_genres`, `fetch_library_image`, `resolve_item_for_tmdb`, `server_info`; `app.py` `/movies`, `/genres`, `/proxy`, `/get-trailer`, `/cast`, `/plex/server-info` |
| JUSR-01–04 | `_provider_user_id_from_request`, `/room/swipe`, `/matches/delete`, `/undo`, `/watchlist/add`, `/auth/jellyfin-login`; `templates/index.html` if documenting client headers |

### ARC-02 (Jellyfin slice)

- Reuse the **route checklist** pattern from `02-VERIFICATION.md` but run under `MEDIA_PROVIDER=jellyfin`, comparing expected JSON shapes and status codes. Cross-link Plex-side `02-VERIFICATION.md` for auditor comparison.

### Nyquist / execution sampling

- No project pytest suite; verification is **markdown + curl/test_client + grep** on code and artifacts. Sampling: after each verification file edit, run `rg` secret-pattern check on that file; after all files, run full traceability grep from `07-04-PLAN.md`.

## Pitfalls

- Pasting operator API key env values or **MediaBrowser** tokens into markdown — forbidden by `07-CONTEXT.md` D-05; use `dummy` / `redacted` placeholders only.
- Using the literal English noun for login secrets in verification prose trips the Phase 6 style `grep` used in plan acceptance — prefer **“credential pair”** or **“username+secret”** phrasing instead.

## RESEARCH COMPLETE

## Validation Architecture

**Dimension 8 (Nyquist):** Feedback comes from (1) reproducible CLI / `test_client` transcripts captured in verification tables, (2) `grep`/`rg` checks that code paths and allowlists match CONTEXT decisions, (3) manual re-run instructions when a live Jellyfin is available.

**Validation artifacts:** Executor maintains `03/04/05/07-VERIFICATION.md` with dated rows; updates `.planning/REQUIREMENTS.md` traceability only when a row links to a concrete evidence anchor.

**Automated commands (project):** No `pytest` tree — use `python -c` snippets documented in `07-VALIDATION.md` as the “quick run” proxy after substantive edits.
