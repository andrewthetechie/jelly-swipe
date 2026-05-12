"""Migration-first application bootstrap for Jelly Swipe."""

from __future__ import annotations

import asyncio

import uvicorn

from jellyswipe.config import AppConfig
from jellyswipe.db_runtime import dispose_runtime, initialize_runtime
from jellyswipe.migrations import upgrade_to_head


def main() -> None:
    """Migrate the target database, initialize async runtime, then start Uvicorn."""
    config = AppConfig()

    upgrade_to_head(config.sync_db_url)

    try:
        asyncio.run(initialize_runtime(config.async_db_url))
        uvicorn.run("jellyswipe:app", host="0.0.0.0", port=5005)
    except Exception:
        asyncio.run(dispose_runtime())
        raise


if __name__ == "__main__":
    main()
