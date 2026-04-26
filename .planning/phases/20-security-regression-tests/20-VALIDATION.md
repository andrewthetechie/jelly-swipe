---
phase: 20
slug: security-regression-tests
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest -q tests/test_route_authorization.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q tests/test_route_authorization.py`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green (or blocker explicitly documented)
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | VER-01 | T-20-01 | Spoofed alias headers rejected on all protected routes with uniform unauthorized contract | route tests | `pytest -q tests/test_route_authorization.py -k spoof` | ❌ W0 | ⬜ pending |
| 20-01-02 | 01 | 1 | VER-02 | T-20-02 | `/room/swipe` body `user_id` injection does not allow unauthorized writes | route + DB assertions | `pytest -q tests/test_route_authorization.py -k injection` | ❌ W0 | ⬜ pending |
| 20-01-03 | 01 | 1 | VER-03 | T-20-03 | Delegate and token valid flows remain functional across protected routes | route tests | `pytest -q tests/test_route_authorization.py -k valid` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_route_authorization.py` — route-level security regression suite for VER-01/02/03
- [ ] Route test fixtures for delegate and token identity paths that avoid `mocker` fixture dependency

---

## Manual-Only Verifications

All phase behaviors target automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
