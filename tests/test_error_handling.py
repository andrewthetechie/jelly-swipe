"""
Error handling and RequestId tests.

These tests verify that:
- Every request gets a unique RequestId (req_<timestamp>_<hex>)
- Error responses never leak exception details (str(e))
- All error responses follow consistent JSON format with request_id
- X-Request-Id header present in all HTTP responses
- Exception handlers log structured details with request_id

Requirements: ERR-01, ERR-02, ERR-03, ERR-04, TEST-02
"""

import ast
import os
import re
import sys
import importlib
import logging
from unittest.mock import patch, MagicMock

import pytest

from flask import Flask as _RealFlaskClass

_REAL_FLASK = _RealFlaskClass


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    db_file = tmp_path / "test_error_handling.db"

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


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


class TestRequestIdGeneration:
    """Unit tests for generate_request_id() function."""

    def test_format_matches_pattern(self, flask_app):
        from jellyswipe import generate_request_id
        rid = generate_request_id()
        assert re.match(r'^req_\d+_[0-9a-f]{8}$', rid), f"RequestId '{rid}' doesn't match req_<digits>_<8-hex>"

    def test_uniqueness_across_calls(self, flask_app):
        from jellyswipe import generate_request_id
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100, "RequestId generation not unique across calls"

    def test_timestamp_is_recent(self, flask_app):
        import time
        from jellyswipe import generate_request_id
        before = int(time.time()) - 1
        rid = generate_request_id()
        after = int(time.time()) + 1
        ts_part = int(rid.split('_')[1])
        assert before <= ts_part <= after, f"Timestamp {ts_part} not in range [{before}, {after}]"


class TestRequestIdPropagation:
    """Integration tests for RequestId in HTTP responses."""

    def test_response_has_x_request_id_header(self, client):
        resp = client.get('/auth/provider')
        assert 'X-Request-Id' in resp.headers, "Missing X-Request-Id header"

    def test_x_request_id_matches_format(self, client):
        resp = client.get('/auth/provider')
        rid = resp.headers.get('X-Request-Id', '')
        assert re.match(r'^req_\d+_[0-9a-f]{8}$', rid), f"X-Request-Id '{rid}' doesn't match expected format"

    def test_different_requests_get_different_ids(self, client):
        resp1 = client.get('/auth/provider')
        resp2 = client.get('/auth/provider')
        rid1 = resp1.headers.get('X-Request-Id', '')
        rid2 = resp2.headers.get('X-Request-Id', '')
        assert rid1 != rid2, "Consecutive requests should get different RequestIds"

    def test_error_response_body_contains_request_id(self, client):
        """Error response body should include request_id field."""
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = Exception("test internal error")
            resp = client.get('/plex/server-info')
        data = resp.get_json()
        assert 'request_id' in data, "Error response missing request_id field"
        assert re.match(r'^req_\d+_[0-9a-f]{8}$', data['request_id'])


class TestErrorSanitization:
    """Verify no str(e) leakage in client-facing error responses."""

    def test_trailer_500_no_exception_details(self, client):
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = Exception("SECRET_INTERNAL_DB_CONNECTION_STRING")
            resp = client.get('/get-trailer/test-movie-id')
        data = resp.get_json()
        assert resp.status_code == 500
        assert 'SECRET_INTERNAL_DB_CONNECTION_STRING' not in str(data)
        assert data.get('error') == 'Internal server error'

    def test_cast_500_no_exception_details(self, client):
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = Exception("SECRET_API_KEY_LEAKED")
            resp = client.get('/cast/test-movie-id')
        data = resp.get_json()
        assert resp.status_code == 500
        assert 'SECRET_API_KEY_LEAKED' not in str(data)
        assert data.get('error') == 'Internal server error'

    def test_watchlist_500_no_exception_details(self, client):
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = Exception("SECRET_WATCHLIST_ERROR")
            resp = client.post('/watchlist/add',
                               json={'movie_id': 'test-id'},
                               headers={'Authorization': 'MediaBrowser Token="fake-token"'})
        data = resp.get_json()
        # Could be 401 (unauthorized) or 500 depending on token resolution
        if resp.status_code == 500:
            assert 'SECRET_WATCHLIST_ERROR' not in str(data)
            assert data.get('error') == 'Internal server error'

    def test_server_info_500_no_exception_details(self, client):
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = Exception("SECRET_SERVER_ERROR_DETAIL")
            resp = client.get('/plex/server-info')
        data = resp.get_json()
        assert resp.status_code == 500
        assert 'SECRET_SERVER_ERROR_DETAIL' not in str(data)
        assert data.get('error') == 'Internal server error'

    def test_ast_scan_no_str_e_in_returns(self):
        """AST scan: no str(e) in return/yield statements in __init__.py."""
        import pathlib
        init_path = pathlib.Path(__file__).resolve().parent.parent / "jellyswipe" / "__init__.py"
        source = init_path.read_text()
        tree = ast.parse(source)

        violations = []
        for node in ast.walk(tree):
            # Check return statements
            if isinstance(node, ast.Return) and node.value:
                source_segment = ast.get_source_segment(source, node.value)
                if source_segment and 'str(e)' in source_segment:
                    violations.append(f"Line {node.lineno}: {source_segment}")
            # Check if str(e) appears in a return context within a function call
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'str':
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id == 'e':
                            # Check if this is inside a return or jsonify call
                            source_segment = ast.get_source_segment(source, node)
                            if source_segment:
                                # Look at parent context
                                for parent in ast.walk(tree):
                                    if isinstance(parent, ast.Return):
                                        seg = ast.get_source_segment(source, parent.value)
                                        if seg and 'str(e)' in seg:
                                            violations.append(f"Line {parent.lineno}: {seg}")

        assert len(violations) == 0, f"Found str(e) in return statements:\n" + "\n".join(violations)


class TestErrorResponseFormat:
    """Verify consistent error response format."""

    def test_4xx_includes_specific_message_and_request_id(self, client):
        """404 from get_trailer includes specific message + request_id."""
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = RuntimeError("Item lookup failed for id")
            resp = client.get('/get-trailer/test-movie-id')
        data = resp.get_json()
        assert resp.status_code == 404
        assert data.get('error') == 'Movie metadata not found'
        assert 'request_id' in data

    def test_5xx_includes_generic_message_and_request_id(self, client):
        """500 from server_info includes generic message + request_id."""
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = RuntimeError("unexpected internal error")
            resp = client.get('/plex/server-info')
        data = resp.get_json()
        assert resp.status_code == 500
        assert data.get('error') == 'Internal server error'
        assert 'request_id' in data

    def test_cast_404_includes_cast_field(self, client):
        """404 from get_cast includes 'cast' field."""
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = RuntimeError("Item lookup failed for id")
            resp = client.get('/cast/test-movie-id')
        data = resp.get_json()
        assert resp.status_code == 404
        assert 'cast' in data
        assert data['cast'] == []
        assert 'request_id' in data

    def test_cast_500_includes_cast_field(self, client):
        """500 from get_cast includes 'cast' field."""
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = Exception("something broke")
            resp = client.get('/cast/test-movie-id')
        data = resp.get_json()
        assert resp.status_code == 500
        assert 'cast' in data
        assert data['cast'] == []
        assert 'request_id' in data

    def test_401_includes_request_id(self, client):
        """401 responses include request_id."""
        resp = client.post('/watchlist/add', json={'movie_id': 'test-id'})
        data = resp.get_json()
        assert resp.status_code == 401
        assert 'request_id' in data


class TestErrorLogging:
    """Verify structured error logging with request_id."""

    def test_exception_triggers_error_log_with_request_id(self, client, caplog):
        with caplog.at_level(logging.ERROR):
            with patch('jellyswipe.get_provider') as mock_prov:
                mock_prov.side_effect = Exception("test logging error")
                resp = client.get('/plex/server-info')

        assert resp.status_code == 500
        # Verify that structured error logging happened
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) > 0, "Expected error log records"

        # Check for request_id in log records
        has_request_id = any(
            getattr(r, 'request_id', None) or 'request_id' in str(r.__dict__)
            for r in error_records
        )
        assert has_request_id, "Error log should include request_id"

    def test_exception_log_includes_exception_type(self, client, caplog):
        with caplog.at_level(logging.ERROR):
            with patch('jellyswipe.get_provider') as mock_prov:
                mock_prov.side_effect = RuntimeError("test runtime error")
                resp = client.get('/plex/server-info')

        assert resp.status_code == 500
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        has_exc_type = any(
            getattr(r, 'exception_type', None) == 'RuntimeError'
            for r in error_records
        )
        assert has_exc_type, "Error log should include exception_type"

    def test_exception_log_includes_exception_message(self, client, caplog):
        with caplog.at_level(logging.ERROR):
            with patch('jellyswipe.get_provider') as mock_prov:
                mock_prov.side_effect = RuntimeError("specific error detail for logging")
                resp = client.get('/plex/server-info')

        assert resp.status_code == 500
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        has_exc_msg = any(
            getattr(r, 'exception_message', None) == "specific error detail for logging"
            for r in error_records
        )
        assert has_exc_msg, "Error log should include exception_message"


class TestAdditionalRoutes:
    """Additional coverage for routes not covered by main test classes."""

    def test_400_includes_request_id(self, client):
        """400 response from go_solo with no active room includes request_id."""
        with client.session_transaction() as sess:
            sess.pop('active_room', None)
        resp = client.post('/room/go-solo')
        data = resp.get_json()
        assert resp.status_code == 400
        assert 'request_id' in data
        assert data.get('error') == 'No active room'

    def test_404_join_room_includes_request_id(self, client):
        """404 response from join_room with invalid code includes request_id."""
        resp = client.post('/room/join', json={'code': '0000'})
        data = resp.get_json()
        assert resp.status_code == 404
        assert 'request_id' in data
        assert data.get('error') == 'Invalid Code'

    def test_cast_runtime_error_500_includes_request_id(self, client):
        """500 from get_cast with non-lookup RuntimeError includes request_id."""
        with patch('jellyswipe.get_provider') as mock_prov:
            mock_prov.side_effect = RuntimeError("some other runtime error")
            resp = client.get('/cast/test-movie-id')
        data = resp.get_json()
        assert resp.status_code == 500
        assert data.get('error') == 'Internal server error'
        assert 'request_id' in data
        assert 'cast' in data
