"""
Smoke tests for test infrastructure (Phase 14).

These tests verify:
- pytest discovers and runs tests from tests/ directory (INFRA-01)
- conftest.py fixtures work correctly (INFRA-02)
- Modules can be imported without Flask app initialization (INFRA-03)
- pytest configuration provides appropriate output (INFRA-04)
"""

import os

def test_module_import():
    """
    Test that jellyswipe modules can be imported without Flask app errors.
    Verifies framework-agnostic imports work (INFRA-03).

    This test passes if:
    - jellyswipe.db imports successfully
    - jellyswipe.jellyfin_library imports successfully
    - No RuntimeError about missing env vars
    - No Flask app is instantiated (conftest.py patches it)
    """
    # These imports should not raise errors because conftest.py:
    # 1. Patches load_dotenv() to skip .env loading
    # 2. Patches Flask() to prevent app initialization
    # 3. Sets required environment variables
    import jellyswipe.db
    import jellyswipe.jellyfin_library

    # Verify the modules have expected exports
    assert hasattr(jellyswipe.db, 'get_db')
    assert hasattr(jellyswipe.db, 'init_db')
    assert hasattr(jellyswipe.jellyfin_library, 'JellyfinLibraryProvider')

def test_env_vars_set():
    """
    Test that required environment variables are set by conftest.py.
    Verifies conftest.py fixtures work (INFRA-02).

    This test passes if:
    - JELLYFIN_URL is set to test value
    - TMDB_API_KEY is set to test value
    - FLASK_SECRET is set to test value
    """
    assert os.getenv("JELLYFIN_URL") == "http://test.jellyfin.local"
    assert os.getenv("TMDB_API_KEY") == "test-tmdb-key"
    assert os.getenv("FLASK_SECRET") == "test-secret-key"
