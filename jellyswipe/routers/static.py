"""Static file serving routes.

Per D-06: 4 static routes serving index.html, manifest.json, sw.js, and favicon.ico.
Uses Jinja2Templates for HTML rendering.
"""

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from starlette.templating import Jinja2Templates

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
static_router = APIRouter()

# Compute app root for static file paths (goes up from routers/ to jellyswipe/)
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Templates directory
templates = Jinja2Templates(directory=os.path.join(_APP_ROOT, 'templates'))


@static_router.get('/')
def index(request: Request):
    """Serve the main index.html page."""
    # Starlette 1.0.0 changed TemplateResponse signature to (request, name, context=None).
    # Old API: TemplateResponse(name, {"request": req, ...})
    # New API: TemplateResponse(request, name, context={...})
    return templates.TemplateResponse(request, 'index.html', {"media_provider": "jellyfin"})


@static_router.get('/manifest.json')
def serve_manifest(request: Request):
    """Serve the PWA manifest.json file."""
    return FileResponse(
        path=os.path.join(_APP_ROOT, 'static', 'manifest.json'),
        media_type='application/manifest+json'
    )


@static_router.get('/sw.js')
def serve_sw(request: Request):
    """Serve the service worker JavaScript file."""
    return FileResponse(
        path=os.path.join(_APP_ROOT, 'static', 'sw.js'),
        media_type='application/javascript'
    )


@static_router.get('/favicon.ico')
def serve_favicon(request: Request):
    """Serve the favicon.ico file."""
    return FileResponse(
        path=os.path.join(_APP_ROOT, 'static', 'favicon.ico'),
        media_type='image/x-icon'
    )
