#!/usr/bin/env bash
set -euo pipefail
# Validation: mirrors .github/workflows/test.yml (the `test` job runs the
# backend pytest suite, the `frontend-test` job runs typecheck/lint/test).
# Exit non-zero if any step fails.

# Backend: unit/integration tests (live Jellyfin cases are deselected in pyproject).
uv run pytest tests/

# Frontend: mirror the CI `frontend-test` job (npm ci -> typecheck -> lint -> test).
cd frontend
npm ci
npm run typecheck
npm run lint
npm test
