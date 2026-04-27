"""
Centralized HTTP client helper with security best practices.

This module provides a single point of control for all outbound HTTP requests,
enforcing consistent timeouts, User-Agent headers, structured logging, and
proper error handling across the application.
"""

import logging
import time
from typing import Dict, Optional, Tuple, Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "JellySwipe/1.6 (+https://github.com/andrewthetechie/jelly-swipe)"
DEFAULT_TIMEOUT = (5, 30)  # (connect, read) in seconds


def make_http_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Tuple[int, int] = DEFAULT_TIMEOUT,
    **kwargs
) -> requests.Response:
    """
    Centralized HTTP request helper with security best practices.

    This function enforces consistent behavior across all HTTP requests:
    - Default timeout to prevent worker exhaustion
    - Consistent User-Agent header for transparency
    - Structured logging for observability
    - Proper exception handling with context preservation

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        url: Request URL
        headers: Request headers (User-Agent will be added if not present)
        params: Query parameters for the request
        json: JSON body for POST/PUT requests
        timeout: (connect, read) timeout tuple in seconds. Defaults to (5, 30).
        **kwargs: Additional arguments passed to requests.request

    Returns:
        requests.Response: The HTTP response object

    Raises:
        requests.exceptions.RequestException: On network errors, timeouts, or HTTP errors
            (includes ConnectionError, Timeout, HTTPError, etc.)

    Example:
        >>> response = make_http_request(
        ...     method='GET',
        ...     url='https://api.example.com/data',
        ...     timeout=(5, 15)
        ... )
        >>> data = response.json()

    Example with JSON body:
        >>> response = make_http_request(
        ...     method='POST',
        ...     url='https://api.example.com/create',
        ...     json={'name': 'test'},
        ...     timeout=(5, 15)
        ... )
        >>> result = response.json()
    """
    start_time = time.time()

    # Ensure User-Agent header
    if headers is None:
        headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = DEFAULT_USER_AGENT

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json,
            timeout=timeout,
            **kwargs
        )

        duration_ms = (time.time() - start_time) * 1000

        # Structured logging for successful requests
        logger.info(
            "http_request",
            extra={
                'method': method,
                'url': url,
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2),
                'success': 200 <= response.status_code < 300
            }
        )

        # Raise HTTP errors for non-2xx responses
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        duration_ms = (time.time() - start_time) * 1000

        # Structured logging for failed requests
        logger.error(
            "http_request_failed",
            extra={
                'method': method,
                'url': url,
                'duration_ms': round(duration_ms, 2),
                'error_type': type(e).__name__,
                'error_message': str(e)
            }
        )

        # Re-raise exception with full context
        raise