"""Domain routers for Jelly Swipe FastAPI application.

This package contains domain-specific routers extracted from the monolithic
__init__.py. Each router handles a specific domain:

- auth.py: Authentication and session management routes
- static.py: Static file serving (index.html, manifest.json, sw.js, favicon.ico)
- media.py: Media-related routes (trailer, cast, genres, watchlist)
- proxy.py: Image proxy for Jellyfin artwork

All routers use APIRouter() with no prefix (D-14) and depend on
jellyswipe.config for shared runtime constants.
"""