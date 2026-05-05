# Phase 36: Alembic Baseline and SQLAlchemy Models - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 36-Alembic Baseline and SQLAlchemy Models
**Areas discussed:** Schema Fidelity, Baseline Strategy, Model Boundaries, Startup Side Effects

---

## Schema Fidelity

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Exact mirror | Preserve current columns, nullability, defaults, and constraints exactly | |
| Tighten obvious gaps | Allow low-risk cleanup while establishing the baseline schema | ✓ |
| Document gaps only | Mirror the schema and defer all tightening to later phases | |

**User's choice:** Tighten obvious gaps
**Notes:** The user wanted Phase 36 to improve the schema where the existing behavior already clearly implies stronger structure.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Indexes only | Add lookup help without relational constraints | |
| Indexes + foreign keys | Add FKs where relationships are already obvious | |
| Indexes + FKs + non-null | Also enforce clearly required values in the baseline | ✓ |

**User's choice:** Indexes + FKs + non-null
**Notes:** Tightening is acceptable when it reflects actual app behavior rather than inventing new requirements.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Table-first only | Columns and constraints only, no ORM relationships | |
| Minimal relationships | Add just enough relationships for clarity | |
| Full ORM graph | Model the full relationship topology for later repository work | ✓ |

**User's choice:** Full ORM graph
**Notes:** Relationship completeness is preferred even though runtime query behavior stays unchanged in this phase.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as Text | Preserve JSON-like columns as `TEXT` | ✓ |
| Use JSON type facade | Expose JSON semantics through SQLAlchemy types | |
| Normalize later | Defer any structure changes entirely | |

**User's choice:** Keep as Text
**Notes:** The user did not want JSON storage changes coupled to this baseline phase.

---

## Baseline Strategy

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Current-state baseline only | Build the new schema directly from one baseline migration | ✓ |
| Baseline plus legacy upgrades | Preserve upgrade logic from older ad hoc schemas | |
| Stamped bootstrap | Assume existing DBs can simply be stamped | |

**User's choice:** Current-state baseline only
**Notes:** The migration should represent the new source of truth rather than encode compatibility history.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Manual reset only | Existing DBs are discarded or recreated | ✓ |
| Stamp and trust | Stamp old DBs without validation | |
| Verify then stamp | Validate shape before stamping | |

**User's choice:** Manual reset only
**Notes:** The user clarified that nobody is running Jelly Swipe and this is effectively a greenfield redesign.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current names | Preserve legacy naming during the transition | |
| Rename obvious mistakes now | Clean up awkward schema naming during the baseline | ✓ |
| Selective cleanup | Mix old and new naming based on churn | |

**User's choice:** Rename obvious mistakes now
**Notes:** Greenfield status removed the main reason to preserve awkward names.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative | Keep the old structure unless cleanup is trivial | |
| Moderate | Improve the relational model without widening phase scope | ✓ |
| Aggressive | Reshape tables freely for future repository work | |

**User's choice:** Moderate
**Notes:** Cleanup should be meaningful but bounded.

---

## Model Boundaries

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Single `models.py` | Put all models in one file for simplicity | |
| Dedicated package | Use a models package with a clean import boundary | ✓ |
| Inside `db.py` | Keep schema types alongside DB runtime code | |

**User's choice:** Dedicated package
**Notes:** The user preferred a durable structure over a one-file bootstrap.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Pure metadata module | Alembic imports only a clean metadata assembly module | ✓ |
| Models package root | Rely on `jellyswipe.models` import side effects | |
| `db.py` export | Let the DB runtime module own metadata | |

**User's choice:** Pure metadata module
**Notes:** Avoid app-import side effects and hidden registration dependencies.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Schema only | Keep the model layer limited to structure | ✓ |
| Light domain helpers | Allow small validation/serialization helpers | |
| Rich model objects | Put domain behavior directly on models | |

**User's choice:** Schema only
**Notes:** Query logic and app behavior should live elsewhere.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| In Alembic only | Handle naming translation only in migration code | ✓ |
| In model mapping | Keep legacy DB names behind cleaned-up Python attributes | |
| Mixed | Preserve some legacy names selectively | |

**User's choice:** No translation layer; use new names directly
**Notes:** The user explicitly rejected compatibility translation because there are no running copies to preserve.

---

## Startup Side Effects

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Split runtime work out | Move maintenance/setup out of `init_db()` and let Alembic own schema creation | ✓ |
| Keep one startup entrypoint | Internally split responsibilities but keep a single orchestration function | |
| Drop most startup work | Reintroduce only what breaks boot or tests | |

**User's choice:** Split runtime work out
**Notes:** Schema bootstrap and runtime maintenance should no longer be coupled.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Runtime PRAGMAs | Keep SQLite PRAGMAs as runtime configuration | ✓ |
| Migration PRAGMAs | Bake them into the baseline migration | |
| Reevaluate later | Avoid carrying them forward automatically | |

**User's choice:** Runtime PRAGMAs
**Notes:** Alembic should not own connection/runtime tuning.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both maintenance functions | Preserve orphan swipe cleanup and token cleanup as explicit runtime work | ✓ |
| Keep token cleanup only | Drop orphan swipe cleanup unless proven necessary | |
| Remove both | Let later phases decide what maintenance remains | |

**User's choice:** Keep both maintenance functions
**Notes:** Cleanup behavior remains part of runtime semantics even though schema creation moves away.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Thin wrapper | Keep a temporary `init_db()` orchestrator | |
| Remove `init_db()` now | Replace it with explicit primitives immediately | ✓ |
| Compatibility facade | Keep `init_db()` until the full async migration is done | |

**User's choice:** Remove `init_db()` now
**Notes:** The user preferred a clean break over a transitional compatibility wrapper.

---

## the agent's Discretion

None.

## Deferred Ideas

None.
