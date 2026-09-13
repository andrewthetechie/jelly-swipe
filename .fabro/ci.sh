#!/usr/bin/env bash
set -euo pipefail
# Validation: unit/integration tests (mirrors .github/workflows/test.yml; live
# Jellyfin cases are deselected in pyproject). Exit non-zero on failure.
uv run pytest tests/
