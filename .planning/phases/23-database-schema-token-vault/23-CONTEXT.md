# Phase 23: Database Schema + Token Vault - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Additive-only schema migration: create `user_tokens` table for server-side Jellyfin token storage, add columns needed by subsequent v2.0 phases (deck state, match metadata, deep links), and implement expired token cleanup. No route changes, no client changes — purely database layer.

**Requirements:** AUTH-02 (token stored in `user_tokens` SQLite table), AUTH-03 (expired rows cleaned up automatically)

</domain>

<decisions>
## Implementation Decisions

### Schema Migration Strategy
- **D-01:** Use existing `init_db()` pattern — `CREATE TABLE IF NOT EXISTS user_tokens` + `PRAGMA table_info` guards for new columns on existing tables. No new migration framework or dedicated `migrate_v2()` function.
- **D-02:** New columns on existing tables are nullable (no NOT NULL constraints) to maintain additive-only migration safety.

### Token Cleanup
- **D-03:** `cleanup_expired_tokens()` runs on BOTH every new session creation (login/delegate) AND on DB init (app startup). This ensures the table stays small during long-running sessions AND gets a fresh sweep on app restart.

### Schema Additions Scope
- **D-04:** Phase 23 proactively adds ALL known v2.0 columns across all tables, even though some won't be used until Phases 24-26. This is safe because all additions are nullable columns and reduce migration churn.
- **D-05:** Known column additions:
  - `user_tokens` table: `session_id TEXT PRIMARY KEY`, `jellyfin_token TEXT`, `jellyfin_user_id TEXT`, `created_at TEXT` (ISO timestamp)
  - `rooms` table: `deck_position TEXT` (JSON per-user cursor, Phase 25), `deck_order TEXT` (server shuffle seed/order, Phase 25)
  - `matches` table: `deep_link TEXT` (Jellyfin URL, Phase 26), `rating TEXT`, `duration TEXT`, `year TEXT` (enriched metadata, Phase 26)

### the agent's Discretion
- Exact `created_at` format (ISO 8601 string vs Unix timestamp)
- Whether `deck_position` stores per-user JSON or a single integer position
- Error handling for migration edge cases (e.g., column already exists from a partial run)

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §Identity & Auth — AUTH-02, AUTH-03 acceptance criteria
- `.planning/ROADMAP.md` §Phase 23 — Success criteria and plan outline
- `.planning/research/SUMMARY.md` §Recommended Stack — user_tokens table design, Flask signed cookies sufficient
- `.planning/research/ARCHITECTURE.md` §Component Boundaries — user_tokens schema, migration strategy

### Existing codebase patterns
- `jellyswipe/db.py` — Current `init_db()` migration pattern using `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`
- `.planning/codebase/ARCHITECTURE.md` — Data layer patterns, SQLite schema conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/db.py:get_db()` — Returns `sqlite3.connect()` with `Row` factory; use for all new queries
- `jellyswipe/db.py:init_db()` — Existing migration pattern to extend with new table + columns

### Established Patterns
- Schema migration: `PRAGMA table_info(table)` → check column list → `ALTER TABLE ADD COLUMN` if missing. All new columns nullable.
- Table creation: `CREATE TABLE IF NOT EXISTS` with inline column definitions
- Cleanup: `DELETE FROM ... WHERE ...` pattern (existing: `DELETE FROM swipes WHERE room_code NOT IN ...`)

### Integration Points
- `jellyswipe/__init__.py:89` — `jellyswipe.db.DB_PATH = DB_PATH` sets the DB path before `init_db()` runs
- `jellyswipe/__init__.py:86` — `from .db import get_db, init_db` — new functions must be importable from `db.py`
- Future phases will import `cleanup_expired_tokens()` and new column accessor functions from `db.py`

</code_context>

<specifics>
## Specific Ideas

- The `user_tokens` table follows the research-recommended "token vault" pattern: session_id as PK, token + user_id as data, created_at for TTL
- All column additions are additive-only — no column renames or type changes to existing columns
- Existing 54+ tests must continue passing after schema migration

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 23-database-schema-token-vault*
*Context gathered: 2026-04-26*
