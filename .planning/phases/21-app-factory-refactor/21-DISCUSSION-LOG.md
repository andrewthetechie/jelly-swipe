# Phase 21: App Factory Refactor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-26
**Phase:** 21 - App Factory Refactor
**Mode:** discuss (no user discussion required)

## Analysis

This phase was analyzed for gray areas requiring user input. Based on codebase analysis and research findings:

### Codebase Analysis

**Current state (jellyswipe/__init__.py):**
- Side-effecting module body with direct Flask app instantiation
- Environment variable validation at import time (raises RuntimeError if missing)
- Global `app` instance created directly, used by Dockerfile/Gunicorn
- Database initialization (`init_db()`) runs at module import
- Provider singleton pattern with module-level `_provider_singleton`
- All routes defined with `@app.route()` decorators on global app

**Testing approach (tests/conftest.py):**
- Framework-agnostic tests that mock Flask entirely
- `setup_test_environment` fixture patches `load_dotenv()` and `Flask()` to prevent side effects
- Environment variables set at module level for all tests
- Function-scoped fixtures for test isolation (db_connection, mock_env_vars)

### Gray Area Assessment

**Assessment:** No user-facing gray areas identified.

**Rationale:**
1. **Success criteria are specific and clear** (FACTORY-01 from REQUIREMENTS.md):
   - `create_app(test_config=None)` factory function
   - Global `app` instance for backwards compatibility
   - Factory accepts test_config parameter
   - No breaking changes

2. **Research confirms standard pattern** (research/SUMMARY.md):
   - App factory is standard Flask pattern, documented in official tutorial
   - No new dependencies required
   - Flask's built-in test client is sufficient

3. **Pure technical refactoring**:
   - No user-facing behavior changes
   - No UI/UX decisions needed
   - No product vision clarification needed
   - Clear backwards compatibility requirement

4. **Implementation is straightforward**:
   - Wrap existing app creation in function
   - Move module-level initialization into factory
   - Keep global `app` for backwards compatibility
   - Standard Flask pattern with well-documented approach

### Decisions Made (without user discussion)

Based on analysis, all implementation decisions were captured directly in CONTEXT.md:

| Decision ID | Decision | Source |
|-------------|----------|--------|
| D-01 | Factory function named `create_app(test_config=None)` | FACTORY-01 requirement |
| D-02 | Factory returns Flask app instance | Research findings |
| D-03 | Uses env vars when test_config is None | Existing production behavior |
| D-04 | Merges test_config for test overrides | Test isolation requirement |
| D-05 | Keep env validation at module import | Early failure in production |
| D-06 | Tests set env vars before calling create_app | Existing conftest.py pattern |
| D-07 | Global app instance preserved | Dockerfile/Gunicorn compatibility |
| D-08 | Global app = create_app() at module level | Backwards compatibility |
| D-09 | All existing imports unchanged | No breaking changes requirement |
| D-10 | init_db() during factory execution | Test isolation |
| D-11 | Tests override DB_PATH via test_config | Fresh databases per test |
| D-12 | Production behavior unchanged | No breaking changes |
| D-13 | Keep provider singleton pattern | Existing code pattern |
| D-14 | No changes to get_provider() logic | Preserve working code |
| D-15 | Routes remain in __init__.py | Minimal refactoring |
| D-16 | Routes register on factory-returned app | Factory pattern requirement |

### Agent Discretion Areas

Left to planner/executor discretion (no user input needed):
- Exact order of operations within `create_app()`
- How test_config is merged (dict.update() vs Flask config methods)
- Whether to extract route registration into separate function

## Discussion Summary

**Areas discussed:** None (no gray areas requiring user input)

**User input received:** None (decisions made based on requirements, research, and codebase analysis)

**Decisions deferred:** None

## External Research Applied

None (all decisions based on existing research and codebase analysis).

## Conclusion

Phase 21 context was created directly without user discussion because:
- All requirements are specific and clear from FACTORY-01 and research
- Implementation is a standard Flask pattern with well-documented approach
- No user-facing decisions needed (pure technical refactoring)
- Backwards compatibility requirement is explicit
- Agent discretion areas are clear and can be resolved during planning/execution

Context is ready for planning phase.

---
*Discussion log: 2026-04-26*
