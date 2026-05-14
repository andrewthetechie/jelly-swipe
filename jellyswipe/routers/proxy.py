"""Image proxy route for Jellyfin artwork.

Per D-06: 1 proxy route with rate limiting.
Serves images from Jellyfin server through the app to avoid exposing server secrets.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from jellyswipe import XSSSafeJSONResponse

from jellyswipe.config import AppConfig, get_config
from jellyswipe.dependencies import check_rate_limit, get_provider
from jellyswipe.schemas.common import ErrorResponse

import requests

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
proxy_router = APIRouter()


@proxy_router.get(
    "/proxy",
    tags=["Proxy"],
    summary="Get image from Jellyfin server",
    responses={
        200: {"content": {"image/*": {}}},
        403: {
            "model": ErrorResponse,
            "description": "Missing, empty, or invalid path parameter; permission denied",
        },
        404: {"model": ErrorResponse, "description": "Image not found in Jellyfin"},
        502: {
            "model": ErrorResponse,
            "description": "Upstream server error from Jellyfin",
        },
    },
)
def proxy(
    request: Request,
    path: str | None = Query(
        None,
        description="Image path in Jellyfin server (format: jellyfin/{media_id}/Primary)",
    ),
    config: AppConfig = Depends(get_config),
    provider=Depends(get_provider),
    _: None = Depends(check_rate_limit),
):
    """Proxy image requests to Jellyfin server with path validation.

    Fetches image data from the configured Jellyfin server and returns it
    as binary image content. The path parameter must match the allowlist regex
    to prevent SSRF attacks:

    - Format: `jellyfin/{media_id}/Primary`
    - media_id: 32-char hex or 36-char UUID
    - Example: `/proxy?path=jellyfin/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4/Primary`

    **Error handling:**

    - Missing or empty path returns 403
    - Path validation failure returns 403
    - Image not found returns 404
    - Jellyfin server errors return 502
    """
    if not path:
        raise HTTPException(status_code=403)
    if not config.jellyfin_url:
        raise HTTPException(status_code=503)
    try:
        body, content_type = provider.fetch_library_image(path)
    except PermissionError:
        raise HTTPException(status_code=403)
    except FileNotFoundError:
        raise HTTPException(status_code=404)
    except requests.exceptions.RequestException as exc:
        _logger.warning("proxy: upstream error fetching %s: %s", path, exc)
        return XSSSafeJSONResponse(
            content={"error": "Upstream server error"}, status_code=502
        )
    return Response(content=body, media_type=content_type)
