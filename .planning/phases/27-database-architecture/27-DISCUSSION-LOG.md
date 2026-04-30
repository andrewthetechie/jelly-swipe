# Phase 27: Database Architecture - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-29
**Phase:** 27-database-architecture
**Mode:** discuss (batch, all areas selected)
**Areas discussed:** WAL Mode Configuration, SSE Persistent Connection, Synchronous Level

## Discussion

### WAL Mode Configuration
| Question | Options Presented | Selected |
|----------|-----------------|----------|
| Where should PRAGMA journal_mode=WAL be set? | (1) In init_db() only (Recommended), (2) In init_db() + every connection | In init_db() only |

**Rationale:** WAL mode is a persistent setting at the database file level. Once set, all subsequent connections automatically use WAL journal mode. Setting it on every connection would be redundant and add overhead.

### SSE Persistent Connection
| Question | Options Presented | Selected |
|----------|-----------------|----------|
| How should the persistent DB connection be managed? | (1) Inline in generator (Recommended), (2) New db.py context manager | Inline in generator |

**Rationale:** Simplest refactor with minimal API surface. Create `sqlite3.connect()` at generator start, close in `finally` block. No new functions needed in `db.py`. Non-SSE routes continue using `get_db_closing()` unchanged.

### Synchronous Level
| Question | Options Presented | Selected |
|----------|-----------------|----------|
| Should sync=NORMAL be set alongside WAL? | (1) Yes, set both (Recommended), (2) WAL only, keep default FULL | Yes, set both |

**Rationale:** `synchronous=NORMAL` is SQLite's recommended setting when using WAL mode. It reduces disk flushes from every commit to WAL checkpoint intervals while maintaining crash recovery. For a home-server app with moderate write volume, this is the right balance of safety and performance.

## Corrections

No corrections — all recommended options were selected.

## Auto-Resolved

N/A — this was an interactive session.

## Prior Decisions Applied

- **Phase 27 SSRF:** "Zero new deps, stdlib only" — applies to this phase (no new pip dependencies)
- **Phase 22 Test Infra:** function-scoped fixtures with `create_app(test_config={})` — WAL mode will automatically apply to temp DBs via `init_db()`
- **Phase 26 Rate Limiter:** New modules go in `jellyswipe/<module>.py` — no new module for this phase, changes are in `db.py` and `__init__.py`

---

*Discussion date: 2026-04-29*