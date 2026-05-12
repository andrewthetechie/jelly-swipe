"""Shared helper functions for router modules."""

import logging
import traceback

from fastapi import Request

from jellyswipe import XSSSafeJSONResponse

_logger = logging.getLogger(__name__)


def make_error_response(
    message: str, status_code: int, request: Request, extra_fields: dict = None
) -> XSSSafeJSONResponse:
    """Create a standardized error response with request ID tracking."""
    if status_code >= 500:
        message = "Internal server error"
    body = {"error": message}
    body["request_id"] = getattr(request.state, "request_id", "unknown")
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)


def log_exception(
    exc: Exception,
    request: Request,
    context: dict = None,
    logger: logging.Logger = None,
) -> None:
    """Log exception with request context."""
    log_data = {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "route": request.url.path,
        "method": request.method,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "stack_trace": traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    target_logger = logger or _logger
    target_logger.error("unhandled_exception", extra=log_data)
