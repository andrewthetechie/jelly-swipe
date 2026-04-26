---
phase: 19
slug: route-authorization-enforcement
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m py_compile jellyswipe/__init__.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m py_compile jellyswipe/__init__.py`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | SEC-03 | T-19-01 | `/room/swipe` ignores body `user_id` and fails unauthorized without verified identity | static + compile | `rg "user_id = _provider_user_id_from_request\\(\\)" jellyswipe/__init__.py && python -m py_compile jellyswipe/__init__.py` | ✅ | ⬜ pending |
| 19-01-02 | 01 | 1 | SEC-04 | T-19-02 | Protected routes return uniform `401` + `{"error":"Unauthorized"}` on unverifiable identity | static + compile | `rg "return jsonify\\(\\{'error': 'Unauthorized'\\}\\), 401" jellyswipe/__init__.py && python -m py_compile jellyswipe/__init__.py` | ✅ | ⬜ pending |
| 19-01-03 | 01 | 1 | SEC-05 | T-19-03 | User-scoped DB queries/mutations remain constrained to verified identity | static + compile | `rg "user_id = _provider_user_id_from_request\\(\\)" jellyswipe/__init__.py && python -m py_compile jellyswipe/__init__.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
