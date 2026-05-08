#!/usr/bin/env bash
# Phase 40 / VAL-04 — static guard for application package only (excludes alembic/).
# Fails if banned sync-SQLite surface or legacy helpers return under jellyswipe/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v rg >/dev/null 2>&1; then
  echo "VAL-04: ripgrep (rg) required — install rg or skip guard in CI intentionally." >&2
  exit 2
fi

fail() {
  echo "Phase 40 VAL-04 violation — $*" >&2
  echo "See .planning/phases/40-full-migration-validation-and-sync-db-removal/40-CONTEXT.md D-05–D-08." >&2
  exit 1
}

run_scan() {
  local pattern=$1 msg=$2
  if rg --glob '*.py' --line-number "${pattern}" jellyswipe/; then
    fail "${msg} (matched ${pattern})"
  fi
}

run_scan '^import sqlite3\\b' 'raw sqlite3 import'
run_scan '^from sqlite3\\b' 'from sqlite3 import'
run_scan 'sqlite3\\.connect\\b' 'sqlite3.connect'
run_scan '\\bget_db_closing\\b' 'legacy get_db_closing seam'
run_scan '\\bSQLModel\\b' 'SQLModel (out of scope v2.1)'
run_scan '^\\s*def\\s+init_db\\b' 'table-creating init_db'

echo "Phase 40 VAL-04 guard OK (jellyswipe/ clean for configured patterns)"
