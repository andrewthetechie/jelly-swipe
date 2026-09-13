#!/usr/bin/env bash
set -euo pipefail
# Idempotent dependency install for jelly-swipe (Python 3.13 / uv).
uv sync --frozen
