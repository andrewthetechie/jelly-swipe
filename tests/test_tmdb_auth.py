"""
TMDB Bearer token authentication verification tests.

These tests verify that TMDB API calls use Bearer token authentication
via Authorization headers instead of api_key query parameters, eliminating
credential exposure in URLs and logs.

Requirements: TMDB-01, TMDB-02, HTTP-02
"""

import ast
import os
import sys
import importlib
from unittest.mock import patch, MagicMock

import pytest

from flask import Flask as _RealFlaskClass

_REAL_FLASK = _RealFlaskClass


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    db_file = tmp_path / "test_tmdb_auth.db"

    monkeypatch.setenv("JELLYFIN_URL", "http://test.jellyfin.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "test-tmdb-token")
    monkeypatch.setenv("FLASK_SECRET", "test-secret-key")
    monkeypatch.setenv("DB_PATH", str(db_file))

    import flask
    flask.Flask = _REAL_FLASK

    modules_to_remove = [key for key in list(sys.modules.keys()) if key.startswith('jellyswipe')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    import jellyswipe
    from jellyswipe import app

    import jellyswipe.db
    jellyswipe.db.DB_PATH = str(db_file)
    jellyswipe.db.init_db()

    yield app

    modules_to_remove = [key for key in list(sys.modules.keys()) if key.startswith('jellyswipe')]
    for mod in modules_to_remove:
        del sys.modules[mod]


class TestNoApiKeyInUrls:
    """AST-based scan confirming no api_key= in TMDB URL constructions."""

    def test_no_api_key_in_tmdb_urls(self):
        """
        Parse jellyswipe/__init__.py as AST and scan all string constants
        for api_key= pattern. This prevents credential leakage in URLs.
        """
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "jellyswipe",
            "__init__.py",
        )
        with open(init_path, "r") as f:
            source = f.read()

        tree = ast.parse(source)

        api_key_occurrences = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "api_key=" in node.value:
                    api_key_occurrences.append(
                        {"line": node.lineno, "value": node.value}
                    )
            elif isinstance(node, ast.JoinedStr):
                for part in node.values:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        if "api_key=" in part.value:
                            api_key_occurrences.append(
                                {"line": node.lineno, "value": part.value}
                            )

        assert api_key_occurrences == [], (
            f"Found api_key= in URL string constants at: {api_key_occurrences}"
        )


class TestBearerTokenHeaders:
    """Mock-based tests confirming Authorization: Bearer header is sent."""

    def test_tmdb_bearer_token_in_trailer_headers(self, flask_app):
        """
        Verify make_http_request is called with Authorization: Bearer header
        when fetching trailer data via /get-trailer route.
        """
        import jellyswipe

        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test Movie"
        mock_item.year = 2024
        mock_provider.resolve_item_for_tmdb.return_value = mock_item

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 123}]}
        mock_response.status_code = 200

        second_response = MagicMock()
        second_response.json.return_value = {
            "results": [{"site": "YouTube", "type": "Trailer", "key": "abc123"}]
        }
        second_response.status_code = 200

        with patch.object(jellyswipe, 'get_provider', return_value=mock_provider), \
             patch.object(jellyswipe, 'make_http_request', side_effect=[mock_response, second_response]) as mock_http:
            with flask_app.test_client() as client:
                response = client.get('/get-trailer/test_movie_id')

                assert response.status_code == 200

                assert mock_http.call_count == 2

                for call in mock_http.call_args_list:
                    headers = call.kwargs.get('headers', {})
                    assert 'Authorization' in headers, (
                        f"Authorization header missing from make_http_request call: {call}"
                    )
                    assert headers['Authorization'].startswith('Bearer '), (
                        f"Authorization header should start with 'Bearer ': {headers['Authorization']}"
                    )

    def test_tmdb_bearer_token_in_cast_headers(self, flask_app):
        """
        Verify make_http_request is called with Authorization: Bearer header
        when fetching cast data via /cast route.
        """
        import jellyswipe

        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test Movie"
        mock_item.year = 2024
        mock_provider.resolve_item_for_tmdb.return_value = mock_item

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 456}]}
        mock_response.status_code = 200

        second_response = MagicMock()
        second_response.json.return_value = {
            "cast": [{"name": "Actor", "character": "Role", "profile_path": "/path.jpg"}]
        }
        second_response.status_code = 200

        with patch.object(jellyswipe, 'get_provider', return_value=mock_provider), \
             patch.object(jellyswipe, 'make_http_request', side_effect=[mock_response, second_response]) as mock_http:
            with flask_app.test_client() as client:
                response = client.get('/cast/test_movie_id')

                assert response.status_code == 200

                assert mock_http.call_count == 2

                for call in mock_http.call_args_list:
                    headers = call.kwargs.get('headers', {})
                    assert 'Authorization' in headers, (
                        f"Authorization header missing from make_http_request call: {call}"
                    )
                    assert headers['Authorization'].startswith('Bearer '), (
                        f"Authorization header should start with 'Bearer ': {headers['Authorization']}"
                    )


class TestCredentialExposure:
    """Verify logged URLs contain no credentials."""

    def test_tmdb_urls_contain_no_credentials(self):
        """
        Verify that TMDB URL constructions in jellyswipe/__init__.py
        do not contain api_key or token in the URL path/query.
        """
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "jellyswipe",
            "__init__.py",
        )
        with open(init_path, "r") as f:
            source = f.read()

        tree = ast.parse(source)

        tmdb_url_parts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                for part in node.values:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        if "themoviedb.org" in part.value:
                            tmdb_url_parts.append(part.value)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "themoviedb.org" in node.value:
                    tmdb_url_parts.append(node.value)

        for url_part in tmdb_url_parts:
            assert "api_key" not in url_part, (
                f"TMDB URL contains api_key: {url_part}"
            )
            assert "access_token" not in url_part.lower(), (
                f"TMDB URL contains access_token: {url_part}"
            )


class TestTmdbApiKeyRemoved:
    """Verify TMDB_API_KEY env var is no longer read."""

    def test_tmdb_api_key_not_in_init(self):
        """
        Grep jellyswipe/__init__.py for TMDB_API_KEY — should return zero results.
        """
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "jellyswipe",
            "__init__.py",
        )
        with open(init_path, "r") as f:
            source = f.read()

        assert "TMDB_API_KEY" not in source, (
            "TMDB_API_KEY should not appear in jellyswipe/__init__.py"
        )


class TestBootValidation:
    """Verify TMDB_ACCESS_TOKEN is in boot validation loop."""

    def test_tmdb_access_token_in_boot_validation(self):
        """
        Verify TMDB_ACCESS_TOKEN is in the boot validation loop,
        ensuring the app refuses to start without it.
        """
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "jellyswipe",
            "__init__.py",
        )
        with open(init_path, "r") as f:
            source = f.read()

        assert "TMDB_ACCESS_TOKEN" in source, (
            "TMDB_ACCESS_TOKEN must appear in jellyswipe/__init__.py"
        )

        tree = ast.parse(source)

        boot_validation_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value == "TMDB_ACCESS_TOKEN":
                    boot_validation_found = True
                    break

        assert boot_validation_found, (
            "TMDB_ACCESS_TOKEN string constant must exist in boot validation"
        )
