"""Tests for the AppConfig pydantic-settings model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from jellyswipe.config import AppConfig, get_config


def _make_config(**overrides: object) -> AppConfig:
    """Helper to construct AppConfig with ALLOW_PRIVATE_JELLYFIN=1."""
    return AppConfig(
        jellyfin_url=overrides.pop("jellyfin_url", "http://test.example.com"),
        jellyfin_api_key=overrides.pop("jellyfin_api_key", "test-key"),
        tmdb_access_token=overrides.pop("tmdb_access_token", "test-token"),
        session_secret=overrides.pop("session_secret", "test-secret"),
        **overrides,
    )


class TestAppConfigConstruction:
    def test_construction_with_all_required_fields_succeeds(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config()
        assert config.jellyfin_url == "http://test.example.com"
        assert config.jellyfin_api_key == "test-key"
        assert config.tmdb_access_token == "test-token"
        assert config.session_secret == "test-secret"

    def test_missing_jellyfin_url_raises_validation_error(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        monkeypatch.delenv("JELLYFIN_URL", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                jellyfin_api_key="k",
                tmdb_access_token="t",
                session_secret="s",
                _env_file=None,  # prevent .env from supplying the missing field
            )
        assert "jellyfin_url" in str(exc_info.value)

    def test_missing_jellyfin_api_key_raises_validation_error(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        monkeypatch.delenv("JELLYFIN_API_KEY", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                jellyfin_url="http://test.example.com",
                tmdb_access_token="t",
                session_secret="s",
                _env_file=None,
            )
        assert "jellyfin_api_key" in str(exc_info.value)

    def test_missing_tmdb_access_token_raises_validation_error(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        monkeypatch.delenv("TMDB_ACCESS_TOKEN", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                jellyfin_url="http://test.example.com",
                jellyfin_api_key="k",
                session_secret="s",
                _env_file=None,
            )
        assert "tmdb_access_token" in str(exc_info.value)

    def test_missing_session_secret_raises_validation_error(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        monkeypatch.delenv("SESSION_SECRET", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                jellyfin_url="http://test.example.com",
                jellyfin_api_key="k",
                tmdb_access_token="t",
                _env_file=None,
            )
        assert "session_secret" in str(exc_info.value)


class TestAppConfigFrozen:
    def test_frozen_raises_on_field_assignment(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config()
        with pytest.raises(ValidationError):
            config.jellyfin_url = "http://new.example.com"


class TestAppConfigSSRF:
    def test_private_ip_url_fails_without_bypass(self, monkeypatch):
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError, match="private IP"):
            AppConfig(
                jellyfin_url="http://192.168.1.1",
                jellyfin_api_key="k",
                tmdb_access_token="t",
                session_secret="s",
            )

    def test_private_ip_url_succeeds_with_bypass(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = AppConfig(
            jellyfin_url="http://192.168.1.1",
            jellyfin_api_key="k",
            tmdb_access_token="t",
            session_secret="s",
        )
        assert config.jellyfin_url == "http://192.168.1.1"


class TestAppConfigComputedFields:
    def test_sync_db_url_with_explicit_db_path(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config(db_path="/tmp/test.db")
        expected = f"sqlite:///{Path('/tmp/test.db').resolve()}"
        assert config.sync_db_url == expected

    def test_async_db_url_with_explicit_db_path(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config(db_path="/tmp/test.db")
        expected = f"sqlite+aiosqlite:///{Path('/tmp/test.db').resolve()}"
        assert config.async_db_url == expected

    def test_sync_db_url_default_resolves_to_data_jellyswipe_db(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config()
        repo_root = Path(__file__).resolve().parent.parent
        expected = f"sqlite:///{repo_root}/data/jellyswipe.db"
        assert config.sync_db_url == expected

    def test_async_db_url_default_matches_sync_with_async_driver(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config()
        assert config.async_db_url == config.sync_db_url.replace(
            "sqlite:///", "sqlite+aiosqlite:///", 1
        )


class TestAppConfigDefaults:
    def test_db_path_defaults_to_empty_string(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config()
        assert config.db_path == ""



class TestAppConfigJellyfinUrl:
    def test_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config(jellyfin_url="http://test.example.com/")
        assert config.jellyfin_url == "http://test.example.com"

    def test_no_trailing_slash_unchanged(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config(jellyfin_url="http://test.example.com")
        assert config.jellyfin_url == "http://test.example.com"


class TestAppConfigNoImportSideEffects:
    def test_importing_module_does_not_require_env_vars(self):
        """Importing jellyswipe.config should not raise even without env vars."""
        import importlib
        import jellyswipe.config

        importlib.reload(jellyswipe.config)


class TestGetConfigDependency:
    def test_get_config_returns_app_state_config(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        config = _make_config()

        class FakeApp:
            state = type("State", (), {"config": config})()

        class FakeRequest:
            app = FakeApp()

        result = get_config(FakeRequest())
        assert result is config
