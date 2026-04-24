# Phase 8 research — E2E and validation hardening

**Question answered:** What do we need to know to plan milestone-level E2E evidence, `01`–`05` validation completion, and re-audit readiness well?

## Current artifact map

| Artifact | Role | Gap vs Phase 8 bar |
|----------|------|-------------------|
| `08-CONTEXT.md` | Locked decisions (doc-first E2E, no CI browser mandate, dual-session Jellyfin, in-place `NN-VALIDATION.md`) | None — plans must trace D-01–D-16 |
| `07-VERIFICATION.md` | Jellyfin parity closure index | Link target from `08-E2E.md`; do not replace with bulk rewrite |
| `03-VERIFICATION.md`, `04-VERIFICATION.md`, `05-VERIFICATION.md` | Runtime evidence for JAUTH/JLIB/JUSR | Source rows for E2E narrative and for new `03-` / `04-` `*-VALIDATION.md` task maps |
| `01-VALIDATION.md`, `02-VALIDATION.md`, `05-VALIDATION.md` | Nyquist contracts | Still `draft` / `nyquist_compliant: false`; Phase 8 completes or N/A-with-rationale per D-10 |
| `03-VALIDATION.md`, `04-VALIDATION.md` | Missing on disk | Must be **created** (mirror `01-` / `07-` structure: infra table, sampling, per-task map, manual matrix, sign-off) |
| `.planning/v1.0-MILESTONE-AUDIT.md` | Pre-closure snapshot | Stale YAML `gaps` / scores vs today’s verification files — refresh in place per D-13 |

## Code touchpoints for doc-first E2E

- **`app.py`:** `MEDIA_PROVIDER`, Jellyfin env validation, routes for room/deck, `/get-trailer/<id>`, `/cast/<id>`, image proxy, server info, user header handling.
- **`media_provider/factory.py`:** `get_provider()` selection.
- **`media_provider/jellyfin_library.py`:** Auth, deck, metadata, list mutations.
- **`templates/index.html`:** Jellyfin vs Plex client auth path (JUSR-03).

Reproducible snippets should prefer **`app.test_client()`** and **`env -i PATH=… HOME=…`** where Phase 3 verification already established the pattern (no secrets in captured output).

## Risk notes

- **Secrets:** Same bar as Phase 7 — negative `grep`/`rg` for `JELLYFIN_API_KEY`, `PLEX_TOKEN`, raw `Authorization:` in new markdown.
- **ARC-02 / Partial rows:** CONTEXT D-06 — Phase 8 documents Jellyfin-forward E2E and **links** Plex evidence in `02-VERIFICATION.md`; do not silently flip `REQUIREMENTS.md` to Done without evidence.
- **No pytest mandate:** `.planning/codebase/TESTING.md` notes no suite; validation tables should use `python -m py_compile`, `rg` traceability, `docker build .` (where already in `05-VALIDATION.md`), and explicit manual operator steps — not fictional Wave 0 pytest unless a plan explicitly opts in.

## Validation Architecture

Phase 8 execution is **documentation-first** with **sampling gates** tied to edited files:

1. **Quick gate (after each task):** `python -m py_compile app.py` when Python files are touched; otherwise `rg` anchors on edited `.planning/**/*.md`.
2. **Traceability gate (after validation / E2E edits):** `rg` for requirement IDs (`CFG-`, `ARC-`, `JAUTH-`, `JLIB-`, `JUSR-`) in the touched `*-VERIFICATION.md` / `*-VALIDATION.md` / `08-E2E.md` as appropriate per file scope.
3. **Secret-negative gate:** `rg -nE "JELLYFIN_API_KEY|PLEX_TOKEN|Authorization:\\s*Bearer" <new/changed md>` must exit **1** for operator-facing narrative files.
4. **Packaging spot-check (JUSR-04 alignment):** `docker build .` after any dependency or `Dockerfile` change; optional final wave for audit plan if unchanged from prior phase — still cite in `08-VALIDATION.md` task map as manual/full.

**Nyquist / Wave 0:** No new automated test framework is required for Phase 8 closure; mark Wave 0 rows **N/A** with rationale where `02-VALIDATION.md` previously assumed future pytest — replace with compile + grep + manual matrix language aligned to `07-VALIDATION.md`.

**Manual-only bucket:** Jellyfin login → room → swipe → trailer/cast remains **operator-run**; the durable record is `08-E2E.md` with dates, environment shape (not values), and links to verification rows.

---

## RESEARCH COMPLETE

Phase 8 can be planned as three waves: (1) `08-E2E.md`, (2) create/finalize `01`–`05` `*-VALIDATION.md`, (3) refresh `v1.0-MILESTONE-AUDIT.md` + optional `REQUIREMENTS.md` pointer line.
