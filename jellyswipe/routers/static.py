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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
static_router = APIRouter()

# Compute app root for static file paths (goes up from routers/ to jellyswipe/)
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@static_router.get("/", include_in_schema=False)
def index(request: Request):
    """Serve the main index.html page from Vite build output.

    Returns 404 if frontend_dist is not available (frontend has not been built).
    """
    frontend_dist = getattr(request.app.state, "frontend_dist", None)
    if frontend_dist is None:
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(
        path=os.path.join(frontend_dist, "index.html"),
        media_type="text/html",
    )


@static_router.get("/manifest.json", include_in_schema=False)
def serve_manifest(request: Request):
    """Serve the PWA manifest.json file."""
    return FileResponse(
        path=os.path.join(_APP_ROOT, "static", "manifest.json"),
        media_type="application/manifest+json",
    )


@static_router.get("/sw.js", include_in_schema=False)
def serve_sw(request: Request):
    """Serve the service worker JavaScript file."""
    return FileResponse(
        path=os.path.join(_APP_ROOT, "static", "sw.js"),
        media_type="application/javascript",
    )


@static_router.get("/favicon.ico", include_in_schema=False)
def serve_favicon(request: Request):
    """Serve the favicon.ico file."""
    return FileResponse(
        path=os.path.join(_APP_ROOT, "static", "favicon.ico"), media_type="image/x-icon"
    )
