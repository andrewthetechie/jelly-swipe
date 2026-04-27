# Phase 28: Coverage Enforcement - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Add `--cov-fail-under=70` to pytest configuration in pyproject.toml so CI fails if total test coverage drops below 70%. This is a configuration-only change — no new tests written. All existing route tests (phases 23-27) and unit tests (phases 15-16) already contribute to coverage.

</domain>

<decisions>
## Implementation Decisions

### Threshold Scope
- **D-01:** Use whole-package `--cov-fail-under=70` — applies to total coverage across all `jellyswipe` modules (currently 75%), not per-file
- **D-02:** Requirement COV-01 targets `jellyswipe/__init__.py` specifically (currently 78%), but enforcing at the package level is simpler and sufficient — `__init__.py` is the largest module so it dominates the total

### Coverage Configuration
- **D-03:** Append `--cov-fail-under=70` to existing `addopts` line in pyproject.toml `[tool.pytest.ini_options]`
- **D-04:** Resulting addopts: `-v --tb=short --cov=jellyswipe --cov-report=term-missing --cov-fail-under=70`
- **D-05:** No separate `[tool.coverage]` section needed — single-line change to existing config

### CI Verification
- **D-06:** No changes to `.github/workflows/tests.yml` — it runs `uv run pytest tests/` which picks up pyproject.toml config automatically
- **D-07:** Build will fail with pytest exit code 1 if coverage drops below 70%

### the agent's Discretion
- Whether to also add `--cov-fail-under` to CI workflow command as an explicit safety net
- Any minor reordering of addopts flags

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Configuration Target
- `pyproject.toml` — `[tool.pytest.ini_options]` section with current addopts line
- `.github/workflows/tests.yml` (inline) — CI workflow runs `uv run pytest tests/`

### Prior Phase Decisions
- `.planning/phases/21-app-factory-refactor/21-CONTEXT.md` — Factory pattern enabling test isolation
- `.planning/phases/22-test-infrastructure-setup/22-CONTEXT.md` — Shared fixtures (app, client, FakeProvider)

### Research
- `.planning/research/SUMMARY.md` — v1.5 research: pytest-cov provides terminal reporting, no extra deps needed

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml:[tool.pytest.ini_options]` — Already has `--cov=jellyswipe --cov-report=term-missing`; just needs `--cov-fail-under=70` appended
- `.github/workflows/tests.yml` — Already runs pytest with uv; picks up pyproject.toml config

### Established Patterns
- **Terminal-only coverage reporting** (Phase 17): `--cov-report=term-missing` — no HTML/XML reports in v1.5
- **pytest-cov for coverage** (Phase 14): `--cov=jellyswipe` reports on entire package

### Integration Points
- `pyproject.toml addopts` — Single source of truth for pytest flags; both local dev and CI read this
- CI workflow — Fails on non-zero pytest exit code; `--cov-fail-under` causes exit code 1 when threshold not met

### Current Coverage Baseline
```
jellyswipe/__init__.py:          78% (408 stmts, 91 missed)
jellyswipe/base.py:             100%
jellyswipe/db.py:                87%
jellyswipe/jellyfin_library.py:  69%
TOTAL:                           75%
Tests: 159 passing
```

</code_context>

<specifics>
## Specific Ideas

No specific requirements — single configuration change following pytest-cov conventions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---
*Phase: 28-coverage-enforcement*
*Context gathered: 2026-04-26*
