"""Tests for health probe endpoints (/healthz and /readyz)."""

from __future__ import annotations

from sqlalchemy import event


class TestHealthz:
    """Tests for GET /healthz liveness probe."""

    def test_healthz_returns_200_with_status_and_version(self, client):
        """GET /healthz returns 200 with status='ok' and a non-empty version string."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_healthz_no_jellyfin_call(self, client, mocker):
        """GET /healthz does not make any HTTP calls to Jellyfin."""
        spy = mocker.patch("requests.get")
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert spy.call_count == 0

    def test_healthz_no_db_queries(self, client, app):
        """GET /healthz does not issue any SQL queries."""
        from jellyswipe.db_runtime import RUNTIME_ENGINE

        select_count = [0]

        def _on_execute(conn, cursor, statement, parameters, context, executemany):
            if "select" in statement.lower():
                select_count[0] += 1

        event.listen(RUNTIME_ENGINE.sync_engine, "before_cursor_execute", _on_execute)
        try:
            resp = client.get("/healthz")
            assert resp.status_code == 200
            assert select_count[0] == 0
        finally:
            event.remove(
                RUNTIME_ENGINE.sync_engine, "before_cursor_execute", _on_execute
            )

    def test_healthz_no_auth_required(self, db_connection, client_real_auth):
        """GET /healthz without session cookie returns 200 (not 401)."""
        # Ensure no session cookie is set
        client_real_auth.cookies.clear()
        resp = client_real_auth.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestReadyz:
    """Tests for GET /readyz readiness probe."""

    def test_readyz_both_ok(self, client, mocker):
        """When both SQLite and Jellyfin are healthy, returns 200 with ok status."""
        mocker.patch("jellyswipe.routers.health._check_sqlite", return_value="ok")
        mocker.patch("jellyswipe.routers.health._check_jellyfin", return_value="ok")
        resp = client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["checks"]["sqlite"] == "ok"
        assert data["checks"]["jellyfin"] == "ok"

    def test_readyz_jellyfin_timeout(self, client, mocker):
        """When Jellyfin times out, returns 503 with degraded status."""
        mocker.patch("jellyswipe.routers.health._check_sqlite", return_value="ok")
        mocker.patch(
            "jellyswipe.routers.health._check_jellyfin",
            return_value="fail: timeout",
        )
        resp = client.get("/readyz")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["sqlite"] == "ok"
        assert data["checks"]["jellyfin"].startswith("fail:")

    def test_readyz_sqlite_failure(self, client, mocker):
        """When SQLite fails, returns 503 with degraded status."""
        mocker.patch(
            "jellyswipe.routers.health._check_sqlite",
            return_value="fail: database error",
        )
        mocker.patch("jellyswipe.routers.health._check_jellyfin", return_value="ok")
        resp = client.get("/readyz")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["sqlite"].startswith("fail:")

    def test_readyz_no_auth_required(self, db_connection, client_real_auth):
        """GET /readyz without session cookie returns 200/503 (not 401)."""
        # Ensure no session cookie is set
        client_real_auth.cookies.clear()
        resp = client_real_auth.get("/readyz")
        # Could be 200 (both healthy) or 503 (one degraded) but never 401
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "checks" in data
