"""Health probe router for liveness and readiness checks.

Provides two unauthenticated endpoints:
- GET /healthz — Liveness probe (never touches Jellyfin or SQLite)
- GET /readyz — Readiness probe (checks SQLite and Jellyfin in parallel)
"""

import asyncio
from importlib.metadata import PackageNotFoundError, version as _pkg_version

import requests
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text

from jellyswipe.config import AppConfig, get_config
from jellyswipe.db_runtime import RUNTIME_ENGINE

try:
    __version__ = _pkg_version("jellyswipe")
except PackageNotFoundError:
    __version__ = "unknown"

health_router = APIRouter()


async def _check_sqlite() -> str:
    """Run SELECT 1 against the configured SQLite engine with 1s timeout."""
    if RUNTIME_ENGINE is None:
        return "fail: database runtime not initialized"
    try:
        async with asyncio.timeout(1):
            async with RUNTIME_ENGINE.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"fail: {exc}"


async def _check_jellyfin(jellyfin_url: str) -> str:
    """Hit Jellyfin's public info endpoint with 2s timeout."""
    try:
        url = f"{jellyfin_url}/System/Info/Public"
        resp = await asyncio.to_thread(requests.get, url, timeout=2)
        if resp.status_code == 200:
            return "ok"
        return f"fail: HTTP {resp.status_code}"
    except Exception as exc:
        return f"fail: {exc}"


@health_router.get("/healthz")
async def healthz() -> dict:
    """Liveness probe — returns 200 with version. Never touches Jellyfin or SQLite."""
    return {"status": "ok", "version": __version__}


@health_router.get("/readyz")
async def readyz(response: Response, config: AppConfig = Depends(get_config)) -> dict:
    """Readiness probe — checks SQLite and Jellyfin in parallel."""
    sqlite_status, jellyfin_status = await asyncio.gather(
        _check_sqlite(),
        _check_jellyfin(config.jellyfin_url),
    )
    ok = sqlite_status == "ok" and jellyfin_status == "ok"
    response.status_code = 200 if ok else 503
    return {
        "status": "ok" if ok else "degraded",
        "checks": {"sqlite": sqlite_status, "jellyfin": jellyfin_status},
    }
