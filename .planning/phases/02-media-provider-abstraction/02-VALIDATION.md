---
phase: 02
slug: media-provider-abstraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (to be added in Wave 0 if not present) |
| **Config file** | `pytest.ini` or `pyproject.toml` — none today |
| **Quick run command** | `pytest -q` (after Wave 0) |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30 seconds (target once suite exists) |

---

## Sampling Rate

- **After every task commit:** `python -m py_compile app.py media_provider/**/*.py` (until pytest exists)
- **After every plan wave:** `pytest -q` when tests exist; else manual Plex smoke from RESEARCH.md parity matrix
- **Before `/gsd-verify-work`:** Full suite must be green when tests exist
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ARC-01 | — | N/A | grep + compile | `rg "get_provider" app.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — Flask app fixture, env for Plex mode with mocked `plexapi`
- [ ] `tests/test_media_provider_contract.py` — smoke that `get_provider()` returns Plex impl when `MEDIA_PROVIDER=plex`
- [ ] `requirements-dev.txt` or optional `[dev]` extra for `pytest` — document in plan if added

*Until Wave 0: use compile + grep + manual Plex checklist from `02-RESEARCH.md`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|---------------|------------|-------------------|
| Room create + swipe + trailer + proxy | ARC-02 | Needs real Plex library | Follow roadmap success criterion 2; compare card JSON fields to pre-refactor baseline |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
