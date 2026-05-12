"""Shared runtime configuration for Jelly Swipe.

This module is the single source of truth for all shared module-level
constants, environment variables, and runtime configuration.

Per D-01 through D-05:
- D-01: config.py is the single source of truth for shared runtime constants
- D-03: Config globals are initialized at import time
- D-04: validate_jellyfin_url() and JELLYFIN_URL both live in config.py
- D-05: Routers import from jellyswipe.config
"""

from pathlib import Path
from typing import Optional
import logging
import os

from dotenv import load_dotenv

# Load environment variables at import time (D-03)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Import validate_jellyfin_url from ssrf_validator module
from jellyswipe.ssrf_validator import validate_jellyfin_url  # noqa: E402

logger = logging.getLogger(__name__)

# Validate required environment variables (same pattern as original monolith)
missing = []
for v in ("TMDB_ACCESS_TOKEN", "FLASK_SECRET"):
    if not os.getenv(v):
        missing.append(v)

if not os.getenv("JELLYFIN_URL", "").strip():
    missing.append("JELLYFIN_URL")
if not os.getenv("JELLYFIN_API_KEY", "").strip():
    missing.append("JELLYFIN_API_KEY")

if missing:
    msg = f"Missing env vars: {missing}"
    if (
        "JELLYFIN_API_KEY" in missing
        and os.getenv("JELLYFIN_USERNAME")
        and os.getenv("JELLYFIN_PASSWORD")
    ):
        msg += (
            ". JELLYFIN_API_KEY is required; username/password authentication has been removed. "
            "Create an API key in your Jellyfin Dashboard → Advanced → API Keys."
        )
    raise RuntimeError(msg)

# SSRF protection: validate JELLYFIN_URL at boot (per D-04)
validate_jellyfin_url(os.getenv("JELLYFIN_URL"))

# Capture validated URL for use throughout the application (D-04)
_JELLYFIN_URL: str = os.getenv("JELLYFIN_URL", "").rstrip("/")

# Public export (routers import JELLYFIN_URL, not _JELLYFIN_URL)
JELLYFIN_URL: str = _JELLYFIN_URL

# TMDB authentication headers (moved from inside create_app to module level)
TMDB_AUTH_HEADERS = {"Authorization": f"Bearer {os.getenv('TMDB_ACCESS_TOKEN')}"}

# JellyfinLibraryProvider singleton (lazy initialization)
# Use TYPE_CHECKING to avoid circular import with jellyfin_library.py
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from jellyswipe.jellyfin_library import JellyfinLibraryProvider

_provider_singleton: Optional["JellyfinLibraryProvider"] = None
