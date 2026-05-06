"""Migration-first application bootstrap for Jelly Swipe."""

from __future__ import annotations

import asyncio

import uvicorn

from jellyswipe.db_runtime import build_async_database_url, dispose_runtime, initialize_runtime
from jellyswipe.migrations import get_database_url, upgrade_to_head


def main() -> None:
    """Migrate the target database, initialize async runtime, then start Uvicorn."""
    sync_url = get_database_url()
    async_url = build_async_database_url(sync_url)

    upgrade_to_head(sync_url)

    try:
        asyncio.run(initialize_runtime(async_url))
        uvicorn.run("jellyswipe:app", host="0.0.0.0", port=5005)
    except Exception:
        asyncio.run(dispose_runtime())
        raise


if __name__ == "__main__":
    main()
