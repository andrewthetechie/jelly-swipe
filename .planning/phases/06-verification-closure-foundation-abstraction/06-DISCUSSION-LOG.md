# Phase 6: Verification closure: foundation + abstraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 06-verification-closure-foundation-abstraction
**Areas discussed:** verification artifact location, evidence bar, requirements status updates, ARC-02 proof depth

---

## Verification Artifact Location

| Option | Description | Selected |
|--------|-------------|----------|
| A | Create `01-VERIFICATION.md` and `02-VERIFICATION.md` in original phase folders, plus optional Phase 6 index summary. | ✓ |
| B | Create only one `06-VERIFICATION.md` in Phase 6. | |
| C | Other custom layout. | |

**User's choice:** A  
**Notes:** User chose phase-native verification artifacts to match audit expectations and preserve per-phase evidence.

---

## Evidence Bar for CFG/ARC

| Option | Description | Selected |
|--------|-------------|----------|
| A | Require live Plex/Jellyfin runtime smoke in Phase 6. | ✓ |
| B | Automated-only checks (compile/grep/harness), no live runtime requirement. | |
| C | Split approach: automation now, full runtime in Phase 8. | |

**User's choice:** A  
**Notes:** User requested stricter proof bar with live runtime smoke during Phase 6 closure.

---

## Requirements Updates During Phase 6

| Option | Description | Selected |
|--------|-------------|----------|
| A | Update `REQUIREMENTS.md` statuses/checkboxes during Phase 6 once evidence exists. | ✓ |
| B | Keep requirements file unchanged until later re-audit. | |

**User's choice:** A  
**Notes:** Requirement status changes should happen in-step with verification evidence capture.

---

## ARC-02 Proof Depth

| Option | Description | Selected |
|--------|-------------|----------|
| A | Full route-level parity checklist now (room/deck, swipe/match sanity, trailer, proxy, server-info). | ✓ |
| B | Lighter contract checks now; full parity later in Phase 8. | |
| C | Other custom depth. | |

**User's choice:** A  
**Notes:** Route-level parity is required in Phase 6, not deferred.

---

## Claude's Discretion

- Verification document formatting and table style.
- Exact command examples/harness style for evidence capture.
- Shape of Phase 6 index summary.

## Deferred Ideas

None.
