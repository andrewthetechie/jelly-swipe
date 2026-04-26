# Phase 20: Security Regression Tests - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 20-security-regression-tests
**Areas discussed:** Route test harness style, spoofed header coverage matrix, `/room/swipe` body `user_id` injection assertions, valid-flow regression scenarios

---

## Route test harness style

| Option | Description | Selected |
|--------|-------------|----------|
| Flask `test_client` + monkeypatch | Route-level contract tests with isolated dependency patching | ✓ |
| Pure helper/unit tests | Faster but less route wiring coverage | |
| Hybrid | Route tests plus selected helper tests | |

**User's choice:** Flask `test_client` route-level tests with monkeypatching  
**Notes:** Prioritizes route behavior confidence for security regressions.

---

## Spoofed header coverage matrix

| Option | Description | Selected |
|--------|-------------|----------|
| Full matrix across all protected routes | Validate every alias header against each protected route | ✓ |
| Representative subset | Cover all headers on fewer routes | |
| Single canonical route | Minimal coverage footprint | |

**User's choice:** Full matrix across all protected routes  
**Notes:** Maximizes regression safety for `VER-01`.

---

## `/room/swipe` body `user_id` injection assertions

| Option | Description | Selected |
|--------|-------------|----------|
| `401` + no write side effects | Assert unauthorized response and no DB writes | ✓ |
| `401` status only | Assert response contract only | |
| Cross-user isolation only | Focus on data boundary checks | |

**User's choice:** `401` plus no write side effects  
**Notes:** Locks both response and data-integrity guarantees for `VER-02`.

---

## Valid-flow regression scenarios

| Option | Description | Selected |
|--------|-------------|----------|
| Delegate + token paths on all protected routes | Strongest valid-flow compatibility guard | ✓ |
| Delegate-only coverage | Reduced path validation | |
| Minimal smoke subset | Fastest but least confidence | |

**User's choice:** Delegate and token happy paths on all protected routes  
**Notes:** Ensures hardening does not break legitimate paths (`VER-03`).

---

## Claude's Discretion

- Test fixture structure and parametrization pattern for maintainability.
- Route-security test module organization.

## Deferred Ideas

None.
