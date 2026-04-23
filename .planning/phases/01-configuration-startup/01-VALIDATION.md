---
phase: 1
slug: configuration-startup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — Wave 0 not installing pytest this phase |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py` |
| **Full suite command** | same as quick + import matrices in PLAN verification |
| **Estimated runtime** | &lt; 5 seconds |

## Sampling Rate

- **After every task commit:** `python -m py_compile app.py`
- **After every plan wave:** Import smoke matrices from `01-PLAN-01.md` / `01-PLAN-02.md` verification sections
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | CFG-01, CFG-02 | T-01 / — | No secrets in new log lines | shell | `python -m py_compile app.py` | ✅ | ⬜ pending |
| 1-02-01 | 02 | 2 | CFG-03 | — | N/A | grep | `grep -q "MEDIA_PROVIDER" README.md` | ✅ | ⬜ pending |

## Wave 0 Requirements

- Existing infrastructure: manual import smoke only for this milestone slice.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Jellyfin boot without Plex vars | CFG-02 | needs crafted env | Export `MEDIA_PROVIDER=jellyfin`, `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `TMDB_API_KEY`, `FLASK_SECRET` only; run `python -c "import app; print(app.MEDIA_PROVIDER)"` |
| README accuracy | CFG-03 | human copy-paste | Follow README minimal Jellyfin snippet in a scratch `.env` |

## Validation Sign-Off

- [ ] All tasks have automated verify or documented manual matrix
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] No watch-mode flags
- [ ] Feedback latency &lt; 5s
- [ ] `nyquist_compliant: true` set in frontmatter when phase completes

**Approval:** pending
