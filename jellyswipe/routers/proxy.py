"""Image proxy route for Jellyfin artwork.

Per D-06: 1 proxy route with rate limiting and regex path validation.
Serves images from Jellyfin server through the app to avoid exposing server secrets.
"""

import logging
import re

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
from jellyswipe import XSSSafeJSONResponse

from jellyswipe.dependencies import check_rate_limit, get_provider
from jellyswipe.config import JELLYFIN_URL

import requests

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
proxy_router = APIRouter()


@proxy_router.get('/proxy')
def proxy(request: Request, _: None = Depends(check_rate_limit)):
    """Proxy image requests to Jellyfin server with path validation."""
    path = request.query_params.get('path')
    if not path:
        raise HTTPException(status_code=403)
    if not JELLYFIN_URL:
        raise HTTPException(status_code=503)
    if not re.match(r"^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$", path):
        raise HTTPException(status_code=403)
    try:
        body, content_type = get_provider().fetch_library_image(path)
    except PermissionError:
        raise HTTPException(status_code=403)
    except FileNotFoundError:
        raise HTTPException(status_code=404)
    except requests.exceptions.RequestException as exc:
        _logger.warning("proxy: upstream error fetching %s: %s", path, exc)
        return XSSSafeJSONResponse(content={"error": "Upstream server error"}, status_code=502)
    return Response(content=body, media_type=content_type)
