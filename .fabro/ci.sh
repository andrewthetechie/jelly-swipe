#!/usr/bin/env bash
set -euo pipefail
# The Test environment is declared in .fabro/test.toml and read through `fabro-io test-env`.
# This repository declares no environment, so the line only exports PATH; it keeps the shape of the others.
test_env=$(fabro-io test-env); eval "$test_env"
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
