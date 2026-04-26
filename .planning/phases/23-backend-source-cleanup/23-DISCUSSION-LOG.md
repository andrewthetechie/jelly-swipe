# Phase 23: Backend Source Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 23-backend-source-cleanup
**Areas discussed:** Route deletion

---

## Route deletion

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the route | Clean break — Phase 24 removes callers, no reason to keep the route | ✓ |
| Rename to /server-info | Preserve endpoint under clean name for future use (health check, debug) | |

**User's choice:** Delete the route (Recommended)
**Notes:** Phase 24 removes `fetchPlexServerId()` and all frontend callers, so the route becomes dead code. No need to preserve.

---

## Agent's Discretion

- db.py stale comments (lines 35, 41) — remove or rewrite the `plex_id` migration comments
- base.py docstring (line 41-42) — update to reference Jellyfin path format instead of Plex `/library/metadata/`

## Deferred Ideas

- Rename `server_info()` method or `machineIdentifier` field — deferred to future cleanup
