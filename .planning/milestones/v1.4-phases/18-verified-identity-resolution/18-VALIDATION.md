---
phase: 18
slug: verified-identity-resolution
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-04-25
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m py_compile jellyswipe/__init__.py jellyswipe/jellyfin_library.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m py_compile jellyswipe/__init__.py jellyswipe/jellyfin_library.py`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | SEC-01 | T-18-01 | Identity resolves only from delegate path or validated token path | static + compile | `python -m py_compile jellyswipe/__init__.py jellyswipe/jellyfin_library.py` | ✅ | ⬜ pending |
| 18-01-02 | 01 | 1 | SEC-02 | T-18-02 | Alias headers cannot establish identity | static | `rg "X-Provider-User-Id|X-Jellyfin-User-Id|X-Emby-UserId" jellyswipe/__init__.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Spoof header request path emits unauthorized response classification | SEC-02 | Requires route-level execution context and auth headers | Use Flask test client or curl against local app to submit spoof headers and verify unauthorized behavior in response payload/status during execution |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
