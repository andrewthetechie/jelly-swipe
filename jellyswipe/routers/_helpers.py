"""Shared helper functions for router modules.

``make_error_response`` and ``log_exception`` live in
``jellyswipe.http_utils`` (neutral ground usable by both routers and
services) and are re-exported here for backward compatibility.
"""

from jellyswipe.http_utils import log_exception, make_error_response

__all__ = ["log_exception", "make_error_response"]
