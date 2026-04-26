# Phase 18: Verified Identity Resolution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 18-verified-identity-resolution
**Areas discussed:** Identity source precedence, Spoofed header handling behavior, Token-to-user-id caching strategy, Authorization header parsing strictness

---

## Identity source precedence

| Option | Description | Selected |
|--------|-------------|----------|
| Delegate first, token second, no other fallback | Use delegated server identity when present; otherwise validate token identity | ✓ |
| Token first, delegate second | Prefer token identity over delegated identity | |
| Require both delegate and token to match | Strict dual-source enforcement | |
| Other | Custom precedence | |

**User's choice:** Delegate first, token second, no other fallback  
**Notes:** Establishes a strict trusted-source chain and removes fallback ambiguity.

---

## Spoofed header handling behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Treat as unauthorized and fail immediately | Fail request if spoofable identity headers are present | ✓ |
| Ignore headers silently and continue | Skip spoof headers and proceed with trusted source resolution | |
| Ignore + add warning log/metric | Continue request but emit observability signal | |
| Other | Custom behavior | |

**User's choice:** Treat as unauthorized and fail immediately  
**Notes:** Chooses explicit security signaling over silent tolerance.

---

## Token-to-user-id caching strategy

| Option | Description | Selected |
|--------|-------------|----------|
| No cache | Always resolve user via Jellyfin API | |
| In-memory cache keyed by token hash with short TTL | Reduce repeated lookups while limiting stale identity windows | ✓ |
| In-memory cache with no TTL until restart | Persist mapping for process lifetime | |
| Other | Custom caching policy | |

**User's choice:** In-memory cache keyed by token hash with short TTL (5 min)  
**Notes:** Balances performance and safety.

---

## Authorization header parsing strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict format only | Reject any non-exact header formatting | |
| Current tolerant parse for `Token="..."`, then validate via Jellyfin | Preserve compatibility while keeping trust at validation step | ✓ |
| Support multiple token syntaxes | Broad compatibility mode | |
| Other | Custom parser behavior | |

**User's choice:** Current tolerant parse for `Token="..."`, then validate via Jellyfin  
**Notes:** Keeps existing compatibility posture while preserving server-side trust checks.

---

## Claude's Discretion

- Cache implementation details (data structure, cleanup timing) within the selected TTL policy.
- Exact unauthorized payload wording and log granularity.

## Deferred Ideas

None.
