"""Route tests for GET /api/v1/version — includes chat_enabled flag."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from pypsa_app.backend.main import app
from pypsa_app.backend.settings import Settings


class TestVersionRouteChatEnabled:
    """The /version endpoint exposes chat_enabled so the frontend can gate UI."""

    def test_chat_enabled_true_when_env_var_set_to_true(self) -> None:
        env = {"CHAT_ENABLED": "true", "SNAKEDISPATCH_BACKENDS": ""}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "pypsa_app.backend.api.routes.version.settings", Settings()
            ):
                client = TestClient(app)
                response = client.get("/api/v1/version/")
                assert response.status_code == 200
                assert response.json()["chat_enabled"] is True

    def test_chat_enabled_false_when_env_var_set_to_false(self) -> None:
        env = {"CHAT_ENABLED": "false", "SNAKEDISPATCH_BACKENDS": ""}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "pypsa_app.backend.api.routes.version.settings", Settings()
            ):
                client = TestClient(app)
                response = client.get("/api/v1/version/")
                assert response.status_code == 200
                assert response.json()["chat_enabled"] is False

    def test_chat_enabled_false_when_env_var_not_set(self) -> None:
        env = {"SNAKEDISPATCH_BACKENDS": ""}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "pypsa_app.backend.api.routes.version.settings", Settings()
            ):
                client = TestClient(app)
                response = client.get("/api/v1/version/")
                assert response.status_code == 200
                assert response.json()["chat_enabled"] is False

    def test_response_keeps_existing_fields_alongside_chat_enabled(self) -> None:
        env = {"CHAT_ENABLED": "true", "SNAKEDISPATCH_BACKENDS": ""}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "pypsa_app.backend.api.routes.version.settings", Settings()
            ):
                client = TestClient(app)
                response = client.get("/api/v1/version/")
                assert response.status_code == 200
                data = response.json()
                expected = {
                    "backend_version",
                    "frontend_app_version",
                    "frontend_map_version",
                    "pypsa_version",
                    "snakedispatch_backends",
                    "chat_enabled",
                }
                assert expected <= set(data.keys())

    def test_no_auth_required_for_version_endpoint(self) -> None:
        env = {"SNAKEDISPATCH_BACKENDS": ""}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "pypsa_app.backend.api.routes.version.settings", Settings()
            ):
                client = TestClient(app)
                response = client.get("/api/v1/version/")
                assert response.status_code == 200
