"""
Migration verification tests for Phase 23.

These tests verify that all HTTP calls now use the centralized make_http_request()
helper function and that no direct requests.get() or requests.post() calls remain.
"""

import ast
import os
from pathlib import Path

import pytest


class TestMigration23:
    """Test suite for verifying Phase 23 migration completion."""

    def test_no_direct_requests_get_calls(self):
        """
        Scan codebase for direct requests.get() calls.
        Verify that all HTTP GET requests use make_http_request() instead.
        """
        # Scan jellyswipe directory for Python files
        jellyswipe_dir = Path(__file__).parent.parent / "jellyswipe"
        python_files = list(jellyswipe_dir.rglob("*.py"))

        direct_requests_calls = []

        for py_file in python_files:
            # Skip http_client.py itself (it's the helper)
            if py_file.name == "http_client.py":
                continue

            content = py_file.read_text()

            # Parse the AST to find actual calls (not just comments or imports)
            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Check for requests.get() calls
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            # Check if it's requests.get or requests.post
                            if (isinstance(node.func.value, ast.Name) and
                                node.func.value.id == 'requests' and
                                node.func.attr in ['get', 'post']):
                                # Get the line number and context
                                line_num = node.lineno
                                lines = content.split('\n')
                                if line_num <= len(lines):
                                    line_content = lines[line_num - 1].strip()
                                    # Skip if it's just a comment
                                    if not line_content.startswith('#'):
                                        direct_requests_calls.append({
                                            'file': str(py_file.relative_to(jellyswipe_dir.parent)),
                                            'line': line_num,
                                            'content': line_content
                                        })
            except SyntaxError:
                # Skip files that can't be parsed (unlikely, but safe to ignore)
                continue

        # Assert no direct requests.get() or requests.post() calls found
        assert len(direct_requests_calls) == 0, (
            f"Found {len(direct_requests_calls)} direct requests.get/post calls:\n" +
            "\n".join([
                f"  - {call['file']}:{call['line']}: {call['content']}"
                for call in direct_requests_calls
            ])
        )

    def test_no_direct_requests_post_calls(self):
        """
        Scan codebase for direct requests.post() calls.
        This is redundant with test_no_direct_requests_get_calls but provides
        explicit test coverage for POST method.
        """
        # The test_no_direct_requests_get_calls already covers both GET and POST
        # This test exists for explicit coverage reporting
        assert True

    def test_make_http_request_importable(self):
        """Verify that make_http_request can be imported and is callable."""
        from jellyswipe.http_client import make_http_request

        # Verify it's callable
        assert callable(make_http_request)

        # Verify it has the expected signature
        import inspect
        sig = inspect.signature(make_http_request)

        # Check required parameters
        assert 'method' in sig.parameters
        assert 'url' in sig.parameters

        # Check optional parameters with defaults
        assert 'headers' in sig.parameters
        assert 'params' in sig.parameters
        assert 'json' in sig.parameters
        assert 'timeout' in sig.parameters

        # Verify timeout has a default value
        assert sig.parameters['timeout'].default is not inspect.Parameter.empty

    def test_all_http_calls_have_timeouts(self):
        """
        Verify that all make_http_request() calls have explicit timeout parameters.
        """
        jellyswipe_dir = Path(__file__).parent.parent / "jellyswipe"
        python_files = list(jellyswipe_dir.rglob("*.py"))

        calls_without_timeout = []

        for py_file in python_files:
            # Skip http_client.py (the helper definition itself)
            if py_file.name == "http_client.py":
                continue

            content = py_file.read_text()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Check for make_http_request() calls
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == 'make_http_request':
                            # Check if timeout parameter is provided
                            has_timeout = False
                            for keyword in node.keywords:
                                if keyword.arg == 'timeout':
                                    has_timeout = True
                                    break

                            if not has_timeout:
                                line_num = node.lineno
                                lines = content.split('\n')
                                if line_num <= len(lines):
                                    line_content = lines[line_num - 1].strip()
                                    calls_without_timeout.append({
                                        'file': str(py_file.relative_to(jellyswipe_dir.parent)),
                                        'line': line_num,
                                        'content': line_content
                                    })
            except SyntaxError:
                continue

        # Assert all make_http_request calls have timeout parameter
        assert len(calls_without_timeout) == 0, (
            f"Found {len(calls_without_timeout)} make_http_request calls without timeout:\n" +
            "\n".join([
                f"  - {call['file']}:{call['line']}: {call['content']}"
                for call in calls_without_timeout
            ])
        )

    def test_jellyswipe_modules_import_http_client(self):
        """
        Verify that main jellyswipe modules can import http_client.
        This ensures no circular import issues.
        """
        # Test __init__.py can import http_client
        import jellyswipe.http_client
        assert hasattr(jellyswipe.http_client, 'make_http_request')

        # Test jellyfin_library.py can import http_client
        import jellyswipe.jellyfin_library
        # If we got here without import errors, the circular import check passed

    def test_http_client_module_structure(self):
        """Verify that http_client.py has the expected structure."""
        from jellyswipe import http_client

        # Check for constants
        assert hasattr(http_client, 'DEFAULT_USER_AGENT')
        assert hasattr(http_client, 'DEFAULT_TIMEOUT')

        # Check for main function
        assert hasattr(http_client, 'make_http_request')

        # Verify constants have expected values
        assert 'JellySwipe' in http_client.DEFAULT_USER_AGENT
        assert isinstance(http_client.DEFAULT_TIMEOUT, tuple)
        assert len(http_client.DEFAULT_TIMEOUT) == 2
        assert all(isinstance(t, (int, float)) for t in http_client.DEFAULT_TIMEOUT)