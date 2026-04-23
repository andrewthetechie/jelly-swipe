# Phase 3: Jellyfin authentication & HTTP client - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.  
> Decisions are captured in `03-CONTEXT.md`.

**Date:** 2026-04-22  
**Phase:** 3 — Jellyfin authentication & HTTP client  
**Mode:** `/gsd-discuss-phase 3 --chain`  
**Areas discussed:** Credentials & headers · Module layout · Token lifecycle · Errors/logging · Phase boundary vs Phase 4

---

## Gray area batch (`--chain` + `defaults` pattern)

| Topic | Recommended option | Selected |
|-------|---------------------|----------|
| Credential paths | Support API key **or** username/password using existing Phase 1 env names; prefer API key flow when both could apply | ✓ |
| Code location | Dedicated module under `media_provider/` + factory returns Jellyfin concrete class | ✓ |
| Token storage | In-memory only; `reset()` clears; re-login on next use | ✓ |
| Error surfaces | Generic messages; no secrets in JSON or logs | ✓ |
| Provider surface vs Phase 4 | Phase 3 = auth + `/Items` proof; full deck/genres/proxy parity explicitly Phase 4 | ✓ |

**User's choice:** `[chain] defaults` — same convention as Phase 2 (`02-DISCUSSION-LOG.md`): accept all recommended options without per-question interactive passes.

**Notes:** Interactive gray-area selection was skipped to keep the `--chain` pipeline unblocked; decisions align with `PROJECT.md`, `REQUIREMENTS.md` JAUTH rows, and Phase 2 provider architecture.

---

## Claude's Discretion

- REST path details, `Session` vs bare `requests`, and exact stub vs partial implementation of `LibraryMediaProvider` methods on Jellyfin for Phase 3 only.

## Deferred Ideas

- See `03-CONTEXT.md` `<deferred>` for Phase 4/5 items.
