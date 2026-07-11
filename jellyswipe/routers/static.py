"""Static file serving routes.

Per D-06: 4 static routes serving index.html, manifest.json, sw.js, and favicon.ico.
Routes are registered conditionally based on frontend_dist availability.
"""

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
static_router = APIRouter()

# Compute app root for static file paths (goes up from routers/ to jellyswipe/)
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_frontend_dist() -> str | None:
    """Find frontend_dist directory with two-path fallback.

    Returns the path to frontend_dist if found, None otherwise.
    Searches: jellyswipe/frontend_dist/ (production/Docker) then ../frontend/dist/ (local dev).
    """
    prod_path = os.path.join(_APP_ROOT, "frontend_dist")
    if os.path.isdir(prod_path):
        return prod_path

    dev_path = os.path.join(_APP_ROOT, "..", "frontend", "dist")
    if os.path.isdir(dev_path):
        return dev_path

    return None


_frontend_dist = _find_frontend_dist()


@static_router.get("/", include_in_schema=False)
def index(request: Request):
    """Serve the main index.html page from Vite build output."""
    if _frontend_dist is None:
        return FileResponse(
            path=os.path.join(_APP_ROOT, "templates", "index.html"),
            media_type="text/html",
        )
    return FileResponse(
        path=os.path.join(_frontend_dist, "index.html"),
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
