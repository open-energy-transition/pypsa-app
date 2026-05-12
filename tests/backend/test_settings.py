"""Tests for backend Settings — auth env-var parsing."""

import os
from unittest.mock import patch

from pypsa_app.backend.settings import Settings


class TestAuthEnvVars:
    def test_auth_enabled_env_var_sets_enable_auth_to_false(self) -> None:
        """AUTH_ENABLED=false env var must set enable_auth to False."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "false"}, clear=True):
            s = Settings()
            assert s.enable_auth is False

    def test_auth_enabled_env_var_sets_enable_auth_to_true(self) -> None:
        """AUTH_ENABLED=true env var must set enable_auth to True."""
        with patch.dict(
            os.environ,
            {
                "AUTH_ENABLED": "true",
                "DATABASE_URL": "postgresql://localhost:5432/test",
                "SESSION_SECRET_KEY": "test-secret-key-not-default",
            },
            clear=True,
        ):
            s = Settings()
            assert s.enable_auth is True

    def test_enable_auth_env_var_still_works(self) -> None:
        """ENABLE_AUTH env var must still work (backward compat)."""
        with patch.dict(
            os.environ,
            {
                "ENABLE_AUTH": "true",
                "DATABASE_URL": "postgresql://localhost:5432/test",
                "SESSION_SECRET_KEY": "test-secret-key-not-default",
            },
            clear=True,
        ):
            s = Settings()
            assert s.enable_auth is True

    def test_enable_auth_defaults_to_false(self) -> None:
        """enable_auth must default to False when no env var is set."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.enable_auth is False
