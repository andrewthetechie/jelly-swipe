"""Frontend build output path resolution utilities."""

import os


def find_frontend_dist_path(app_root: str) -> str | None:
    """Find frontend_dist directory with two-path fallback.

    Returns the path to frontend_dist if found, None otherwise.
    Searches: jellyswipe/frontend_dist/ (production/Docker) then ../frontend/dist/ (local dev).

    Args:
        app_root: The jellyswipe package root directory (typically __file__ dirname).

    Returns:
        Absolute path to frontend_dist if found, None otherwise.
    """
    prod_path = os.path.join(app_root, "frontend_dist")
    if os.path.isdir(prod_path):
        return prod_path

    dev_path = os.path.join(app_root, "..", "frontend", "dist")
    if os.path.isdir(dev_path):
        return dev_path

    return None
