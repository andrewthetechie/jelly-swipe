# Phase 06 — Research: verification closure (foundation + abstraction)

## What “good verification” looks like for this repo

Kino Swipe is a small Flask monolith (`app.py`) with **no established automated test harness** in `requirements.txt` (see `.planning/codebase/STACK.md`). Phase 6 is explicitly **evidence-first closure**: verification artifacts must be readable by humans and milestone auditors, and must map each requirement ID to **observed outcomes** (pass/fail/partial) with enough detail to reproduce.

## Evidence classes (recommended mix)

1. **Deterministic preflight checks** (fast): `python -m py_compile …`, targeted `grep`/`rg` checks for wiring and guard strings.
2. **Live runtime smoke** (required by `06-CONTEXT.md` D-03/D-04): start the app with real env against a reachable **Plex** server and a reachable **Jellyfin** server (two separate runs/instances aligns with product decision), then exercise HTTP routes and browser-visible flows.
3. **Route-level parity checklist for Plex** (required by `06-CONTEXT.md` D-05): document end-to-end checks that cover deck load, swipe/match sanity, trailer/cast, proxy image, and `/plex/server-info` JSON shape.

## Pitfalls to avoid

- **Secret leakage in verification logs**: never paste tokens/passwords/API keys into verification tables; reference “redacted” and use safe excerpts only.
- **`.env` contamination**: Phase 1 summaries already note `python-dotenv` can mask missing env tests; verification procedures should call out `env -i` patterns where strict isolation matters.
- **Claiming ARC-02 without route proof**: compile/grep alone is insufficient given Phase 6 decisions; verification must include explicit route checklist results.

## Validation Architecture

Phase 6 validation is intentionally **manual-first** with **deterministic guardrails**:

- **Wave 0 / quick loop:** `python -m py_compile app.py media_provider/*.py` after any doc edits that might accompany evidence capture scripts (if added later).
- **Wave / plan loop:** after each plan wave, re-run quick compile + re-read verification tables for consistency (requirement IDs, status columns, evidence links).
- **Manual-only matrix:** live Plex and live Jellyfin smokes belong in `01-VERIFICATION.md` / `02-VERIFICATION.md` manual tables, not assumed as CI.

Sampling expectations:

- After each task commit: quick compile (if code touched) + confirm verification tables updated.
- After each plan wave: ensure `06-VERIFICATION.md` index matches the phase-native verification statuses.

## Outputs

This research informs:

- `06-VALIDATION.md` — sampling expectations and manual-only matrix rows.
- `06-01-PLAN.md` / `06-02-PLAN.md` / `06-03-PLAN.md` — executable closure steps and verifiable acceptance criteria.

## RESEARCH COMPLETE
