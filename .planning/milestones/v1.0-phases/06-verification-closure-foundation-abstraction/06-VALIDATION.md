---
phase: 06
slug: verification-closure-foundation-abstraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — repo has no pytest harness in `requirements.txt` today |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py media_provider/*.py` |
| **Full suite command** | quick compile + manual verification table review in `01-VERIFICATION.md` / `02-VERIFICATION.md` |
| **Estimated runtime** | < 30 seconds (compile) + manual smoke time varies |

---

## Sampling Rate

- **After every task commit:** `python -m py_compile app.py media_provider/*.py` (if any Python file changed)
- **After every plan wave:** verify `06-VERIFICATION.md` index matches per-phase verification statuses
- **Before `/gsd-verify-work`:** manual tables must contain dated evidence rows for all required live smokes (per `06-CONTEXT.md`)
- **Max feedback latency:** compile checks < 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | CFG-01 | T-06-01 / — | Do not record secrets in verification tables | shell | `test -f .planning/phases/01-configuration-startup/01-VERIFICATION.md` | ✅ | ⬜ pending |
| 06-01-02 | 01 | 1 | CFG-02 | T-06-01 / — | Do not record secrets in verification tables | manual | operator-recorded evidence rows | ✅ | ⬜ pending |
| 06-01-03 | 01 | 1 | CFG-03 | — | N/A | manual | README/compose operator checks | ✅ | ⬜ pending |
| 06-02-01 | 02 | 1 | ARC-01 | — | N/A | shell | `test -f .planning/phases/02-media-provider-abstraction/02-VERIFICATION.md` | ✅ | ⬜ pending |
| 06-02-02 | 02 | 1 | ARC-02 | T-06-01 / — | Do not paste tokens in evidence | manual | Plex route-level checklist | ✅ | ⬜ pending |
| 06-02-03 | 02 | 1 | ARC-03 | — | N/A | shell | `test -f media_provider/jellyfin_library.py` | ✅ | ⬜ pending |
| 06-03-01 | 03 | 2 | CFG/ARC rollup | — | N/A | shell | `test -f .planning/phases/06-verification-closure-foundation-abstraction/06-VERIFICATION.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infrastructure: manual verification tables + compile checks only for this phase slice.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Jellyfin mode boots without Plex vars | CFG-02 | needs crafted env | Run with only Jellyfin + global vars; confirm process starts; capture safe logs |
| Plex mode parity route checklist | ARC-02 | needs real Plex library | Host + browser: room create, deck thumbs, swipe, trailer/cast, proxy image, server-info JSON |
| Jellyfin mode fail-fast before Phases 3–4 completeness | ARC (roadmap success criterion) | depends on provider guard | Start app in jellyfin mode and confirm expected fail-fast vs partial routes per roadmap intent |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or documented manual matrix
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for compile checks
- [ ] `nyquist_compliant: true` set in frontmatter when phase completes

**Approval:** pending
