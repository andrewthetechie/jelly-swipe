# Phase 19: Route Authorization Enforcement - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 19-route-authorization-enforcement
**Areas discussed:** Unauthorized response contract, `/room/swipe` body `user_id` policy, identity-rejection reason exposure, `/matches` unauthorized behavior, rollout mode

---

## Unauthorized response contract

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform `401` with `{ "error": "Unauthorized" }` | One consistent unauthorized payload for protected routes | ✓ |
| Uniform `401` with route-specific messages | More route detail in error payloads | |
| Keep mixed payloads/statuses | Preserve current behavior per route | |
| Other | Custom contract | |

**User's choice:** Uniform `401` with `{ "error": "Unauthorized" }`  
**Notes:** Prioritizes consistency and predictable client handling.

---

## `/room/swipe` body `user_id` policy

| Option | Description | Selected |
|--------|-------------|----------|
| Ignore `user_id` field, always use verified identity | Treat body identity as non-authoritative input | ✓ |
| Reject request if `user_id` is present | Strict anti-tampering gate | |
| Temporarily allow if value matches verified identity | Compatibility compromise | |
| Other | Custom policy | |

**User's choice:** Ignore body `user_id` and use verified identity only  
**Notes:** Removes fallback trust without introducing compatibility blockers for clients still sending the field.

---

## Identity-rejection reason exposure

| Option | Description | Selected |
|--------|-------------|----------|
| Do not expose reason codes to clients | Keep detailed auth reasons internal | ✓ |
| Expose compact reason codes | Client-visible machine-readable auth reasons | |
| Expose full internal reason strings | Maximum transparency to clients | |
| Other | Custom exposure policy | |

**User's choice:** No client exposure of reason codes  
**Notes:** Reduces information disclosure risk.

---

## `/matches` unauthorized behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Strict `401` | Align `/matches` with protected-route unauthorized semantics | ✓ |
| Keep empty-array compatibility | Preserve legacy behavior | |
| Feature-flag compatibility mode | Transitional migration path | |
| Other | Custom behavior | |

**User's choice:** Strict `401`  
**Notes:** Eliminates silent unauthorized reads.

---

## Rollout mode

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate enforcement on all protected routes | No feature-flag transition period | ✓ |
| Feature-flag opt-in rollout | Conservative migration path | |
| Feature-flag opt-out fallback | New behavior default with rollback path | |
| Other | Custom rollout strategy | |

**User's choice:** Immediate enforcement  
**Notes:** Prefers direct remediation over staged rollout.

---

## Claude's Discretion

- Internal helper structure for reusing unauthorized responses.
- Internal observability for rejection reasons.

## Deferred Ideas

None.
