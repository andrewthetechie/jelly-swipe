#!/usr/bin/env bash
set -euo pipefail
# The Test environment is declared in .fabro/test.toml and read through `fabro-io test-env`.
# This repository declares no environment, so the line only exports PATH; it keeps the shape of the others.
test_env=$(fabro-io test-env); eval "$test_env"
# Validation: mirrors .github/workflows/test.yml (the `test` job's phase guard and
# backend pytest; the `frontend-test` job's typecheck/lint/test; the `frontend-build`
# job's build). Exit non-zero if any step fails.

# Backend: the repo's own phase guard, then unit/integration tests (live Jellyfin
# cases are deselected in pyproject).
bash scripts/phase40_val04_guard.sh
uv run pytest tests/

# Frontend: mirror the CI `frontend-test` and `frontend-build` jobs
# (npm ci -> typecheck -> lint -> test -> build).
cd frontend
npm ci
npm run typecheck
npm run lint
npm test
npm run build
