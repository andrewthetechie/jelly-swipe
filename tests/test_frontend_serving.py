"""Tests for conditional frontend dist serving (Vite build output).

Covers issues #201/#204: the "/" route and "/assets" mount must behave
conditionally based on whether the frontend build output is available, and the
two must agree (resolving dist presence once per app instance via
app.state.frontend_dist rather than once at module import).
"""

import os

import pytest
from fastapi.testclient import TestClient

from jellyswipe.utils.frontend import find_frontend_dist_path

# ---------------------------------------------------------------------------
# Unit tests for find_frontend_dist_path
# ---------------------------------------------------------------------------


def test_find_frontend_dist_path_returns_none_when_absent(tmp_path):
    app_root = tmp_path / "pkg"
    app_root.mkdir()
    assert find_frontend_dist_path(str(app_root)) is None


def test_find_frontend_dist_path_prod_takes_precedence(tmp_path):
    app_root = tmp_path / "pkg"
    app_root.mkdir()
    (app_root / "frontend_dist").mkdir()
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    result = find_frontend_dist_path(str(app_root))
    assert result == str(app_root / "frontend_dist")


def test_find_frontend_dist_path_dev_fallback(tmp_path):
    app_root = tmp_path / "pkg"
    app_root.mkdir()
    dev_dist = tmp_path / "frontend" / "dist"
    dev_dist.mkdir(parents=True)
    result = find_frontend_dist_path(str(app_root))
    assert os.path.realpath(result) == os.path.realpath(str(dev_dist))


# ---------------------------------------------------------------------------
# Route-level tests: GET / and /assets conditional on dist availability
# ---------------------------------------------------------------------------


def _make_dist(dist_root):
    """Create a fake Vite dist tree with index.html and an assets/ file."""
    (dist_root / "index.html").write_text(
        "<!DOCTYPE html><html><body>SPA</body></html>"
    )
    assets = dist_root / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app');")


@pytest.fixture
def make_frontend_app(tmp_path, monkeypatch):
    """Factory that builds an app with find_frontend_dist_path controlled.

    Returns a callable taking a dist path (str) or None. Each call yields a
    TestClient whose app resolved dist presence exactly once in create_app().
    """
    import jellyswipe.dependencies as deps
    from jellyswipe import create_app
    from jellyswipe.dependencies import get_provider
    from jellyswipe.rate_limiter import rate_limiter as _rl
    from tests.conftest import (
        FakeProvider,
        _bootstrap_temp_db_runtime,
        _dispose_test_runtime,
        _make_test_config,
    )

    def _factory(dist_path):
        db_path = str(tmp_path / f"test-{dist_path is None}.db")
        _bootstrap_temp_db_runtime(db_path)
        monkeypatch.setattr(
            "jellyswipe.utils.frontend.find_frontend_dist_path",
            lambda app_root: dist_path,
        )
        config = _make_test_config(db_path)
        app = create_app(config=config)
        fake_provider = FakeProvider()
        deps._provider_singleton = fake_provider
        app.dependency_overrides[get_provider] = lambda: fake_provider
        _rl.reset()
        return app

    yield _factory
    _dispose_test_runtime()
    deps._provider_singleton = None


def _client(app):
    cm = TestClient(app)
    return cm


def test_get_index_404_when_frontend_dist_absent(make_frontend_app):
    app = make_frontend_app(None)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 404


def test_get_index_200_when_frontend_dist_present(make_frontend_app, tmp_path):
    dist = tmp_path / "fake_dist"
    dist.mkdir()
    _make_dist(dist)
    app = make_frontend_app(str(dist))
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "SPA" in resp.text


def test_assets_route_404_when_frontend_dist_absent(make_frontend_app):
    app = make_frontend_app(None)
    with TestClient(app) as client:
        resp = client.get("/assets/app.js")
    assert resp.status_code == 404


def test_assets_route_200_when_frontend_dist_present(make_frontend_app, tmp_path):
    dist = tmp_path / "fake_dist"
    dist.mkdir()
    _make_dist(dist)
    app = make_frontend_app(str(dist))
    with TestClient(app) as client:
        resp = client.get("/assets/app.js")
    assert resp.status_code == 200


def test_index_and_assets_consistent_across_create_app(tmp_path, monkeypatch):
    """The dist presence seen by "/" must match the one seen by "/assets".

    Guards against the import-time (static.py) vs per-call (__init__.py)
    divergence: a second create_app() with a different dist must not see the
    first call's cached resolution on either route.
    """
    dist = tmp_path / "fake_dist"
    dist.mkdir()
    _make_dist(dist)

    import jellyswipe.dependencies as deps
    from jellyswipe import create_app
    from jellyswipe.dependencies import get_provider
    from jellyswipe.rate_limiter import rate_limiter as _rl
    from tests.conftest import (
        FakeProvider,
        _bootstrap_temp_db_runtime,
        _dispose_test_runtime,
        _make_test_config,
    )

    db_path = str(tmp_path / "consistency.db")
    _bootstrap_temp_db_runtime(db_path)
    try:
        # dist present
        monkeypatch.setattr(
            "jellyswipe.utils.frontend.find_frontend_dist_path",
            lambda app_root: str(dist),
        )
        config = _make_test_config(db_path)
        app_present = create_app(config=config)
        app_present.dependency_overrides[get_provider] = lambda: FakeProvider()
        _rl.reset()

        # dist absent
        monkeypatch.setattr(
            "jellyswipe.utils.frontend.find_frontend_dist_path",
            lambda app_root: None,
        )
        app_absent = create_app(config=config)
        app_absent.dependency_overrides[get_provider] = lambda: FakeProvider()
        _rl.reset()

        with TestClient(app_present) as c:
            assert c.get("/").status_code == 200
            assert c.get("/assets/app.js").status_code == 200

        with TestClient(app_absent) as c:
            assert c.get("/").status_code == 404
            assert c.get("/assets/app.js").status_code == 404

        deps._provider_singleton = None
    finally:
        _dispose_test_runtime()


def test_traversal_attempt_returns_404(make_frontend_app, tmp_path):
    """Path traversal in the filename parameter must not reach the filesystem.

    Guards CodeQL py/path-injection on the /{filename} route: the whitelist
    gate rejects non-constant filenames, and the resolved-path containment
    check backs it up.
    """
    dist = tmp_path / "fake_dist"
    dist.mkdir()
    _make_dist(dist)
    (tmp_path / "secret.txt").write_text("should not be served")
    app = make_frontend_app(str(dist))
    with TestClient(app) as client:
        assert client.get("/../secret.txt").status_code == 404
        assert client.get("/%2E%2E%2Fsecret.txt").status_code == 404


def test_symlink_escape_returns_404(make_frontend_app, tmp_path):
    """A whitelisted filename that is a symlink escaping frontend_dist must 404.

    The containment check (resolve + is_relative_to) rejects symlinks whose
    target resolves outside the dist root, even when the link name passes the
    whitelist.
    """
    dist = tmp_path / "fake_dist"
    dist.mkdir()
    _make_dist(dist)
    target = tmp_path / "secret.txt"
    target.write_text("should not be served")
    (dist / "icon-192.png").symlink_to(target)
    (dist / "sw.js").symlink_to(target)
    app = make_frontend_app(str(dist))
    with TestClient(app) as client:
        assert client.get("/icon-192.png").status_code == 404
        assert client.get("/sw.js").status_code == 404
