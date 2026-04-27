# Phase 24: TMDB Security - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 24-CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-26
**Phase:** 24-tmdb-security
**Mode:** discuss (--all)

## Discussion Flow

### Area 1: TMDB v4 vs v3 Migration Strategy

**Q: How should we authenticate with TMDB?**

| Option | Description |
|--------|-------------|
| v4 Bearer token only (Recommended) | New env var TMDB_ACCESS_TOKEN, remove TMDB_API_KEY entirely. Cleanest security. |
| v4 preferred, v3 fallback | Try TMDB_ACCESS_TOKEN first, fall back to TMDB_API_KEY in header. |
| v3 header-only | Keep TMDB_API_KEY but move from URL to Authorization header. |

**Selected:** v4 Bearer token only (Recommended)

**Notes:** Cleanest security posture. No key in URLs. Operators get a clear Read Access Token from TMDB settings.

---

### Area 2: Backward Compatibility Handling

**Q: How should the app handle existing operators who only have TMDB_API_KEY configured?**

| Option | Description |
|--------|-------------|
| Hard break — clear error (Recommended) | App refuses to start if TMDB_ACCESS_TOKEN missing. Clear error message. |
| Deprecation period | Accept TMDB_API_KEY temporarily, log deprecation warning. |
| Silent fallback | Try TMDB_ACCESS_TOKEN first, fall back silently. |

**Selected:** Hard break — clear error (Recommended)

**Notes:** Simplest implementation. v1.6 is already a security milestone — clean break is appropriate.

---

### Area 3: Log Redaction

**Q: The v4 migration removes api_key from URLs. How careful should we be about logging the Authorization header?**

| Option | Description |
|--------|-------------|
| Clean URLs, no extra work (Recommended) | URLs clean. Ensure Authorization header never logged. Current http_client.py doesn't log headers. |
| Explicit header sanitization | Add header stripping in http_client.py. Extra safety net. |
| Full redaction filter | Redact headers and URL params that look like tokens. Belt-and-suspenders. |

**Selected:** Clean URLs, no extra work (Recommended)

**Notes:** v4 Bearer auth solves the root problem (credentials in URLs). http_client.py already doesn't log headers. Add a verification test.

---

### Area 4: Documentation & Config Updates

**Q: The TMDB_API_KEY → TMDB_ACCESS_TOKEN rename touches 6+ files. How thorough should this phase be?**

| Option | Description |
|--------|-------------|
| Update all in this phase (Recommended) | Update README, docker configs, Unraid template, lint script, and test fixtures. One commit. |
| Code only, docs later | Only update code and tests. Leave docs for a separate pass. |

**Selected:** Update all in this phase (Recommended)

**Notes:** Consistent state after one phase. 8 files total need TMDB_API_KEY → TMDB_ACCESS_TOKEN updates.

---

## Summary

| Area | Decision |
|------|----------|
| Authentication | v4 Bearer token only |
| Compatibility | Hard break with clear error |
| Log redaction | No extra work needed (clean URLs) |
| Documentation | Update all files in this phase |

---

*Discussion log created: 2026-04-26*
