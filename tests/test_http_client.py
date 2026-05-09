"""
Unit tests for the centralized HTTP client helper.

Tests cover timeout enforcement, User-Agent header setting, structured logging,
exception handling, and various HTTP methods.
"""

import logging
import pytest
from unittest.mock import patch, Mock
import requests

from jellyswipe.http_client import (
    make_http_request,
    DEFAULT_USER_AGENT,
    DEFAULT_TIMEOUT,
)


class TestMakeHttpRequest:
    """Test suite for make_http_request function."""

    def test_make_http_request_sets_default_user_agent(self, caplog):
        """Verify that User-Agent header is added if not provided."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            make_http_request(method="GET", url="https://api.example.com/test")

            # Verify User-Agent header was set
            call_args = mock_request.call_args
            assert "headers" in call_args.kwargs
            assert call_args.kwargs["headers"]["User-Agent"] == DEFAULT_USER_AGENT

    def test_make_http_request_respects_custom_user_agent(self, caplog):
        """Verify that custom User-Agent is preserved when provided."""
        custom_ua = "MyCustomAgent/1.0"

        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            make_http_request(
                method="GET",
                url="https://api.example.com/test",
                headers={"User-Agent": custom_ua},
            )

            # Verify custom User-Agent was used
            call_args = mock_request.call_args
            assert call_args.kwargs["headers"]["User-Agent"] == custom_ua

    def test_make_http_request_enforces_timeout(self):
        """Verify that timeout is passed to requests.request."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            custom_timeout = (3, 10)
            make_http_request(
                method="GET", url="https://api.example.com/test", timeout=custom_timeout
            )

            # Verify timeout was passed
            call_args = mock_request.call_args
            assert call_args.kwargs["timeout"] == custom_timeout

    def test_make_http_request_uses_default_timeout(self):
        """Verify that default timeout is used when not specified."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            make_http_request(method="GET", url="https://api.example.com/test")

            # Verify default timeout was used
            call_args = mock_request.call_args
            assert call_args.kwargs["timeout"] == DEFAULT_TIMEOUT

    def test_make_http_request_logs_success(self, caplog):
        """Verify that successful requests are logged with correct fields."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            with caplog.at_level(logging.INFO):
                make_http_request(method="GET", url="https://api.example.com/test")

            # Verify logging occurred
            assert len(caplog.records) >= 1
            log_record = caplog.records[0]
            assert log_record.levelname == "INFO"
            assert log_record.message == "http_request"
            assert log_record.method == "GET"
            assert log_record.url == "https://api.example.com/test"
            assert log_record.status_code == 200
            assert "duration_ms" in log_record.__dict__
            assert log_record.success is True

    def test_make_http_request_logs_failure(self, caplog):
        """Verify that failed requests are logged with correct fields."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )

            with caplog.at_level(logging.ERROR):
                with pytest.raises(requests.exceptions.ConnectionError):
                    make_http_request(method="GET", url="https://api.example.com/test")

            # Verify error logging occurred
            assert len(caplog.records) >= 1
            log_record = caplog.records[0]
            assert log_record.levelname == "ERROR"
            assert log_record.message == "http_request_failed"
            assert log_record.method == "GET"
            assert log_record.url == "https://api.example.com/test"
            assert "duration_ms" in log_record.__dict__
            assert log_record.error_type == "ConnectionError"
            assert log_record.error_message == "Connection refused"

    def test_make_http_request_re_raises_exceptions(self):
        """Verify that exceptions are re-raised with full context."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(requests.exceptions.Timeout) as exc_info:
                make_http_request(method="GET", url="https://api.example.com/test")

            # Verify exception was re-raised
            assert "Request timed out" in str(exc_info.value)

    def test_make_http_request_get_method(self):
        """Verify that GET method works correctly."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            response = make_http_request(
                method="GET", url="https://api.example.com/test"
            )

            # Verify GET method was used
            call_args = mock_request.call_args
            assert call_args.kwargs["method"] == "GET"
            assert response.json() == {"data": "test"}

    def test_make_http_request_post_method(self):
        """Verify that POST method works correctly."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 123}
            mock_request.return_value = mock_response

            json_body = {"name": "test", "value": 42}
            response = make_http_request(
                method="POST", url="https://api.example.com/create", json=json_body
            )

            # Verify POST method and JSON body were used
            call_args = mock_request.call_args
            assert call_args.kwargs["method"] == "POST"
            assert call_args.kwargs["json"] == json_body
            assert response.json() == {"id": 123}

    def test_make_http_request_with_params(self):
        """Verify that query parameters work correctly."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_request.return_value = mock_response

            params = {"page": 1, "limit": 10}
            response = make_http_request(
                method="GET", url="https://api.example.com/search", params=params
            )

            # Verify params were passed
            call_args = mock_request.call_args
            assert call_args.kwargs["params"] == params
            assert response.json() == {"results": []}

    def test_make_http_request_with_json_body(self):
        """Verify that JSON body works correctly."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"created": True}
            mock_request.return_value = mock_response

            json_data = {"title": "Test Movie", "year": 2024}
            response = make_http_request(
                method="POST", url="https://api.example.com/movies", json=json_data
            )

            # Verify JSON body was passed
            call_args = mock_request.call_args
            assert call_args.kwargs["json"] == json_data
            assert response.json() == {"created": True}

    def test_make_http_request_raises_http_error(self):
        """Verify that HTTP errors (4xx, 5xx) are raised."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "404 Not Found"
            )
            mock_request.return_value = mock_response

            with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                make_http_request(method="GET", url="https://api.example.com/notfound")

            # Verify HTTP error was raised
            assert "404 Not Found" in str(exc_info.value)

    def test_make_http_request_empty_headers_dict(self):
        """Verify that empty headers dict works correctly."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            make_http_request(
                method="GET", url="https://api.example.com/test", headers={}
            )

            # Verify User-Agent was added even with empty dict
            call_args = mock_request.call_args
            assert call_args.kwargs["headers"]["User-Agent"] == DEFAULT_USER_AGENT

    def test_make_http_request_with_additional_kwargs(self):
        """Verify that additional kwargs are passed through."""
        with patch("jellyswipe.http_client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            make_http_request(
                method="GET",
                url="https://api.example.com/test",
                allow_redirects=False,
                verify=False,
            )

            # Verify additional kwargs were passed
            call_args = mock_request.call_args
            assert call_args.kwargs["allow_redirects"] is False
            assert call_args.kwargs["verify"] is False
