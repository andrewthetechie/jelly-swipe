#!/usr/bin/env bash
# Formatters and machine-applicable lint fixes ONLY (fabro-workflows ADR 0011 D5).
# fabro's `autofix` stage runs this after every coder or rework stage, before
# .fabro/ci.sh validates the change. No step may change behaviour or generate code.
# ci.sh is the real gate, so every step runs even if an earlier one fails and this
# script always exits 0.
set -u

# The files this branch touches: committed since origin/main, plus anything not yet
# committed. Deleted files are left out, since there is nothing to fix in them.
changed=$( {
  git diff --name-only --diff-filter=d origin/main...HEAD 2>/dev/null
  git diff --name-only --diff-filter=d HEAD 2>/dev/null
  git ls-files --others --exclude-standard 2>/dev/null
} | sort -u)
changed_py=$(printf '%s\n' "$changed" | grep -E '\.pyi?$' || true)

# Ruff, scoped to this branch's Python files. main is NOT clean under ruff (56
# `ruff check` findings and 4 unformatted files on 2026-10-11), so running it over
# the whole tree would rewrite unrelated files and inflate the PR diff. Safe fixes
# only: --unsafe-fixes stays off. --force-exclude keeps pyproject's alembic/versions
# exclusion in force for paths passed explicitly. Same order as .pre-commit-config.yaml:
# lint fixes first, then format.
if [ -n "$changed_py" ]; then
  # shellcheck disable=SC2086
  uv run ruff check --fix --force-exclude $changed_py || true
  # shellcheck disable=SC2086
  uv run ruff format --force-exclude $changed_py || true
fi

# ESLint --fix over the frontend. main is clean under `npm run lint` (ci.sh gates on
# it), so a whole-tree run only touches what this branch introduced. Rule fixes are
# safe fixes; suggestions are never applied by --fix. setup.sh installs no Node
# dependencies and ci.sh runs `npm ci` after this script, so install them here when
# they are missing.
if [ -d frontend ]; then
  (
    cd frontend || exit 0
    [ -d node_modules ] || npm ci --no-audit --no-fund || exit 0
    npx eslint --fix .
  ) || true
fi

exit 0
