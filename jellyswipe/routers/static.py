"""Static file serving routes.

Per D-06: 4 static routes serving index.html, manifest.json, sw.js, and favicon.ico.
Routes serving Vite build output (index.html, /assets) are only functional when
frontend_dist is available; absent frontend returns 404.

The frontend_dist path is resolved exactly once per app instance in create_app()
(see jellyswipe/__init__.py) and stored on app.state.frontend_dist. Reading it
per-request from app.state keeps the "/" route and the "/assets" mount
consistent within a single app instance instead of letting the two resolve at
different times (module-import vs. create_app call).
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
static_router = APIRouter()

# Compute app root for static file paths (goes up from routers/ to jellyswipe/)
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PWA_ROOT_FILES = {
    "index.html": "text/html",
    "sw.js": "application/javascript",
    "registerSW.js": "application/javascript",
    "manifest.webmanifest": "application/manifest+json",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
}


def _get_static_file_response(filename: str, request: Request) -> FileResponse:
    frontend_dist = getattr(request.app.state, "frontend_dist", None)
    if frontend_dist is None:
        raise HTTPException(status_code=404, detail="Frontend build not found")

    media_type = _PWA_ROOT_FILES.get(filename)
    if media_type is None:
        raise HTTPException(status_code=404, detail="Not Found")
    path = os.path.join(frontend_dist, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path=path, media_type=media_type)


@static_router.get("/{filename}", include_in_schema=False)
def serve_dist_root(filename: str, request: Request):
    """Serve Vite/PWA build artifacts emitted to the dist root."""
    return _get_static_file_response(filename, request)


@static_router.get("/favicon.ico", include_in_schema=False)
def serve_favicon(request: Request):
    frontend_dist = getattr(request.app.state, "frontend_dist", None)
    if frontend_dist is None:
        raise HTTPException(status_code=404, detail="Frontend build not found")
    assets_dir = Path(frontend_dist) / "assets"
    matches = list(assets_dir.glob("favicon-*.png"))

    if not matches:
        raise FileNotFoundError("No favicon-*.png found")

    if len(matches) > 1:
        raise RuntimeError(f"Expected one favicon, found {len(matches)}")

    return FileResponse(path=matches[0], media_type="image/x-icon")


@static_router.get("/", include_in_schema=False)
def serve_index(request: Request):
    return _get_static_file_response("index.html", request)
