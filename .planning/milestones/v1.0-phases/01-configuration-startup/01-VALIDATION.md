---
phase: 1
slug: configuration-startup
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — Wave 0 does not introduce pytest for this milestone slice |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py` |
| **Full suite command** | same as quick + manual matrices documented in `01-*-PLAN.md` verification sections and README |
| **Estimated runtime** | &lt; 5 seconds (automated portion) |

## Sampling Rate

- **After every task commit:** `python -m py_compile app.py`
- **After every plan wave:** Import smoke matrices from `01-PLAN-01.md` / `01-PLAN-02.md` verification sections
- **Before `/gsd-verify-work`:** Automated quick gate green; manual rows executed or marked N/A with rationale
- **Max feedback latency:** 5 seconds (automated)

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | CFG-01, CFG-02 | T-01 / — | No secrets in new log lines | shell | `python -m py_compile app.py` | ✅ | ✅ green |
| 1-02-01 | 02 | 2 | CFG-03 | — | N/A | grep | `grep -q "MEDIA_PROVIDER" README.md` | ✅ | ✅ green |

## Wave 0 Requirements

- [x] **N/A — pytest not used for Phase 1 closure** — No `tests/` tree; gates are `python -m py_compile app.py` and documented manual env/README checks below. Not an open dependency.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Jellyfin boot without Plex vars | CFG-02 | needs crafted env | Export `MEDIA_PROVIDER=jellyfin`, `JELLYFIN_URL`, auth bundle, `TMDB_API_KEY`, `FLASK_SECRET` only; run `python -c "import app; print(app.MEDIA_PROVIDER)"` |
| README accuracy | CFG-03 | human copy-paste | Follow README minimal Jellyfin snippet in a scratch `.env` |

## Validation Sign-Off

- [x] All tasks have automated verify or documented manual matrix
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (compile/grep gates between manual-only rows)
- [x] No watch-mode flags
- [x] Feedback latency &lt; 5s for automated gates
- [x] `nyquist_compliant: true` set in frontmatter when phase completes

**Approval:** approved 2026-04-24
