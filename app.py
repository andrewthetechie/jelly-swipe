"""
Jelly Swipe — Flask application (legacy entry point).

This file is a temporary shim for backward compatibility.
The actual Flask app lives in the jellyswipe package.

Per PKG-01, server code lives under jellyswipe/ and this file
will be removed or become a documented thin re-export after
all imports are updated in a later plan.
"""

from jellyswipe import app  # noqa: F401

__all__ = ["app"]
