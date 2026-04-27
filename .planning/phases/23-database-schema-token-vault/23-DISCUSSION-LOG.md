# Phase 23: Database Schema + Token Vault - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 23-database-schema-token-vault
**Areas discussed:** Schema Migration Strategy, Token Cleanup Trigger, Schema Additions Scope

---

## Schema Migration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Same pattern | CREATE TABLE IF NOT EXISTS + PRAGMA guards in init_db() | ✓ |
| Separate migration | Dedicated migrate_v2() function | |
| You decide | Either approach works | |

**User's choice:** Same pattern
**Notes:** Consistent with existing codebase, no new tooling needed.

---

## Token Cleanup Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| On login | Cleanup when new session created | |
| On DB init | Cleanup on app startup | |
| Both | Cleanup on login AND app startup | ✓ |

**User's choice:** Both
**Notes:** Ensures table stays small during long sessions AND gets swept on restart.

---

## Schema Additions Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Proactive | Add all known v2.0 columns now | ✓ |
| Just-in-time | Each phase adds its own columns | |
| You decide | Either approach works | |

**User's choice:** Proactive
**Notes:** All additions are nullable columns, so additive-only is safe. Reduces migration churn across phases.

---

## the agent's Discretion

- Exact created_at format (ISO 8601 string vs Unix timestamp)
- deck_position storage format (per-user JSON vs single integer)
- Error handling for migration edge cases

## Deferred Ideas

None — discussion stayed within phase scope.
