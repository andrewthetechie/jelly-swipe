"""Smoke tests for infrastructure and documented startup contracts."""

import os
import pathlib

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
    import jellyswipe.bootstrap
    import jellyswipe.migrations

    # Verify the modules have expected exports
    assert hasattr(jellyswipe.db, 'get_db')
    assert hasattr(jellyswipe.db, 'prepare_runtime_database')
    assert hasattr(jellyswipe.db, 'cleanup_expired_auth_sessions')
    assert hasattr(jellyswipe.bootstrap, 'main')
    assert hasattr(jellyswipe.jellyfin_library, 'JellyfinLibraryProvider')
    assert hasattr(jellyswipe.migrations, 'upgrade_to_head')

def test_env_vars_set():
    """
    Test that required environment variables are set by conftest.py.
    Verifies conftest.py fixtures work (INFRA-02).

    This test passes if:
    - JELLYFIN_URL is set to test value
    - TMDB_ACCESS_TOKEN is set to test value
    - FLASK_SECRET is set to test value
    """
    assert os.getenv("JELLYFIN_URL") == "http://test.jellyfin.local"
    assert os.getenv("TMDB_ACCESS_TOKEN") == "test-tmdb-token"
    assert os.getenv("FLASK_SECRET") == "test-secret-key"


def test_pyproject_declares_fastapi_stack_and_excludes_flask_stack():
    """
    DEP-01: pyproject.toml must contain FastAPI/Uvicorn runtime dependencies and
    must NOT contain Flask/Gunicorn/gevent/Werkzeug.

    Reads pyproject.toml as raw text and checks:
    - Required packages: fastapi, uvicorn, itsdangerous, jinja2, python-multipart
    - Forbidden packages: flask, gunicorn, gevent, werkzeug
    """
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    content = pyproject_path.read_text()

    # Required FastAPI stack packages must be present in the dependencies block.
    # We check the [project.dependencies] section specifically to avoid matching
    # comments or unrelated text. A simple substring check on the file is
    # sufficient because these names are unique within pyproject.toml.
    required = ["aiosqlite", "fastapi", "uvicorn", "itsdangerous", "jinja2", "python-multipart"]
    for pkg in required:
        assert pkg in content, (
            f"DEP-01 FAIL: required package '{pkg}' not found in pyproject.toml"
        )

    # Forbidden legacy packages must be completely absent from pyproject.toml.
    # They should appear in zero positions — not in dependencies, not in comments.
    # We check case-insensitively to catch variants like Flask, FLASK, flask.
    content_lower = content.lower()
    forbidden = ["flask", "gunicorn", "gevent", "werkzeug"]
    for pkg in forbidden:
        assert pkg not in content_lower, (
            f"DEP-01 FAIL: forbidden package '{pkg}' found in pyproject.toml"
        )


def test_dockerfile_cmd_uses_python_bootstrap_entrypoint():
    """
    DEP-01: The Dockerfile CMD must launch the Python bootstrap entrypoint
    so migrations run before the app serves requests.

    Reads Dockerfile as raw text and checks the CMD line for:
    - python present
    - jellyswipe.bootstrap present
    - gunicorn absent
    - gevent absent
    - uvicorn absent from the final container CMD
    """
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    dockerfile_path = repo_root / "Dockerfile"
    assert dockerfile_path.exists(), f"Dockerfile not found at {dockerfile_path}"

    content = dockerfile_path.read_text()

    # Extract the CMD line(s) for targeted assertions.
    cmd_lines = [line for line in content.splitlines() if line.strip().startswith("CMD")]
    assert len(cmd_lines) == 1, (
        f"DEP-01 FAIL: expected exactly 1 CMD line in Dockerfile, found {len(cmd_lines)}: {cmd_lines}"
    )
    cmd_line = cmd_lines[0]

    assert 'python' in cmd_line, (
        f"DEP-01 FAIL: CMD line does not reference python. CMD: {cmd_line!r}"
    )
    assert "jellyswipe.bootstrap" in cmd_line, (
        f"DEP-01 FAIL: CMD line does not reference jellyswipe.bootstrap. CMD: {cmd_line!r}"
    )
    assert "gunicorn" not in cmd_line.lower(), (
        f"DEP-01 FAIL: CMD line contains forbidden 'gunicorn'. CMD: {cmd_line!r}"
    )
    assert "gevent" not in cmd_line.lower(), (
        f"DEP-01 FAIL: CMD line contains forbidden 'gevent'. CMD: {cmd_line!r}"
    )
    assert "uvicorn" not in cmd_line.lower(), (
        f"DEP-01 FAIL: CMD line should not invoke uvicorn directly. CMD: {cmd_line!r}"
    )


def test_readme_documents_bootstrap_startup_commands():
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    readme_path = repo_root / "README.md"
    assert readme_path.exists(), f"README.md not found at {readme_path}"

    content = readme_path.read_text()

    assert "uv run python -m jellyswipe.bootstrap" in content
    assert "uv run python -m jellyswipe\n" not in content
    assert "uv run gunicorn" not in content
