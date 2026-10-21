#!/usr/bin/env bash
set -euo pipefail
# Idempotent dependency install for jelly-swipe (Python 3.13 / uv, frontend npm).
uv sync --frozen
# Task validation's frontend checks and the frontend target run before ci.sh's own
# `npm ci`, so the frontend's dependencies are installed here too. The image's npm
# cache is warm, so this is offline.
(cd frontend && npm ci --prefer-offline --no-audit --no-fund)
