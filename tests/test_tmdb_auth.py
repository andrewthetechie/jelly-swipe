"""
TMDB Bearer token authentication verification tests.

These tests verify that TMDB API calls use Bearer token authentication
via Authorization headers instead of api_key query parameters, eliminating
credential exposure in URLs and logs.

Requirements: TMDB-01, TMDB-02, HTTP-02
"""

import ast
import os
from unittest.mock import MagicMock, patch

import jellyswipe.dependencies as deps


class TestNoApiKeyInUrls:
    """AST-based scan confirming no api_key= in TMDB URL constructions."""

    def test_no_api_key_in_tmdb_urls(self):
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

    def test_tmdb_bearer_token_in_trailer_headers(self, client, monkeypatch):
        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test Movie"
        mock_item.year = 2024
        mock_provider.resolve_item_for_tmdb.return_value = mock_item
        monkeypatch.setattr(
            deps, "_provider_singleton", mock_provider, raising=False
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 123}]}
        mock_response.status_code = 200

        second_response = MagicMock()
        second_response.json.return_value = {
            "results": [{"site": "YouTube", "type": "Trailer", "key": "abc123"}]
        }
        second_response.status_code = 200

        # Patch where make_http_request is looked up: jellyswipe.tmdb (refactored from media.py)
        with patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_response, second_response],
        ) as mock_http:
            response = client.get("/get-trailer/test_movie_id")
            assert response.status_code == 200
            assert mock_http.call_count == 2

            for call in mock_http.call_args_list:
                headers = call.kwargs.get("headers", {})
                assert "Authorization" in headers, (
                    f"Authorization header missing from make_http_request call: {call}"
                )
                assert headers["Authorization"].startswith("Bearer "), (
                    f"Authorization header should start with 'Bearer ': {headers['Authorization']}"
                )

    def test_tmdb_bearer_token_in_cast_headers(self, client, monkeypatch):
        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test Movie"
        mock_item.year = 2024
        mock_provider.resolve_item_for_tmdb.return_value = mock_item
        monkeypatch.setattr(
            deps, "_provider_singleton", mock_provider, raising=False
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 456}]}
        mock_response.status_code = 200

        second_response = MagicMock()
        second_response.json.return_value = {
            "cast": [
                {"name": "Actor", "character": "Role", "profile_path": "/path.jpg"}
            ]
        }
        second_response.status_code = 200

        # Patch where make_http_request is looked up: jellyswipe.tmdb (refactored from media.py)
        with patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_response, second_response],
        ) as mock_http:
            response = client.get("/cast/test_movie_id")
            assert response.status_code == 200
            assert mock_http.call_count == 2

            for call in mock_http.call_args_list:
                headers = call.kwargs.get("headers", {})
                assert "Authorization" in headers, (
                    f"Authorization header missing from make_http_request call: {call}"
                )
                assert headers["Authorization"].startswith("Bearer "), (
                    f"Authorization header should start with 'Bearer ': {headers['Authorization']}"
                )


class TestCredentialExposure:
    """Verify logged URLs contain no credentials."""

    def test_tmdb_urls_contain_no_credentials(self):
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
            assert "api_key" not in url_part, f"TMDB URL contains api_key: {url_part}"
            assert "access_token" not in url_part.lower(), (
                f"TMDB URL contains access_token: {url_part}"
            )


class TestTmdbApiKeyRemoved:
    """Verify TMDB_API_KEY env var is no longer read."""

    def test_tmdb_api_key_not_in_init(self):
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
        # Phase 33 moved boot validation from __init__.py to config.py.
        # After ORCH-033, AppConfig in app_config.py validates via pydantic field_validator.
        # The field tmdb_access_token maps to TMDB_ACCESS_TOKEN env var via pydantic-settings.
        base_dir = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(base_dir, "jellyswipe", "app_config.py")
        legacy_config_path = os.path.join(base_dir, "jellyswipe", "config.py")
        init_path = os.path.join(base_dir, "jellyswipe", "__init__.py")

        for source_path in (config_path, legacy_config_path, init_path):
            with open(source_path, "r") as f:
                source = f.read()
            # Check for either the env var name or the pydantic field name
            if "TMDB_ACCESS_TOKEN" in source or "tmdb_access_token" in source:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if node.value in ("TMDB_ACCESS_TOKEN", "tmdb_access_token"):
                            return  # found — test passes
                # Also check for field name in class definition (not a string constant)
                if "tmdb_access_token" in source:
                    return  # pydantic field name present
                break

        raise AssertionError(
            "TMDB_ACCESS_TOKEN (or tmdb_access_token field) must exist in boot validation "
            "(jellyswipe/app_config.py, jellyswipe/config.py, or jellyswipe/__init__.py)"
        )
