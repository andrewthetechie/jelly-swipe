# Phase 24: Auth Module + Server-Owned Identity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-27
**Phase:** 24-auth-module-server-identity
**Mode:** discuss (--all --batch)
**Areas discussed:** Session cookie security flags, Token validity/staleness handling, Login response contract, Session ID lifecycle

## Update Context

Phase 24 had existing context (gathered 2026-04-26). User chose "Update it" to revise and add new decisions.

## Questions and Answers

### Batch 1 (4 questions)

| # | Area | Question | Options Presented | Selected |
|---|------|----------|-------------------|----------|
| 1 | Session cookie security | Configure Secure=True and SameSite=Lax now or defer to Phase 28? | Do it now / Defer to Phase 28 | Do it now |
| 2 | Token validity | Trust vault or validate with Jellyfin on every request? | (A) Trust vault / (B) Validate every request | (A) Trust vault |
| 3 | Login response | Return {userId, displayName} or {userId} only? | {userId, displayName} / {userId} only | {userId} only |
| 4 | Session ID timing | When to create session_id? | (A) On login only / (B) On first page load | (A) On login only |

## Changes from Previous Context

- **D-01 updated:** Login response changed from `{userId, displayName}` to `{userId}` only
- **D-13 added:** Session cookie security flags (Secure=True, SameSite=Lax) configured in Phase 24
- **D-14 added:** Token validity — trust vault, no per-request Jellyfin validation
- **D-15 added:** Session ID created on login only, no anonymous vault entries

## Prior Decisions Carried Forward (unchanged)

D-02 through D-12 from original context remain unchanged.

---

*Discussion log: 2026-04-27*
