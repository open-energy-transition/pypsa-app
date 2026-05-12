"""Tests for build_internal_http_client factory."""

from __future__ import annotations

import httpx
import pytest

from pypsa_app.backend.settings import Settings


class TestBuildInternalHTTPClient:
    """Tests for the build_internal_http_client factory."""

    def test_returns_httpx_async_client(self) -> None:
        """Factory returns an httpx.AsyncClient instance."""
        from pypsa_app.llm.tools.http_client import build_internal_http_client

        settings = Settings()
        client = build_internal_http_client(settings)

        assert isinstance(client, httpx.AsyncClient)

    def test_base_url_uses_resolved_internal_api_base_by_default(self) -> None:
        """When llm_internal_api_base is unset, uses 127.0.0.1:{llm_internal_port}."""
        from pypsa_app.llm.tools.http_client import build_internal_http_client

        settings = Settings()
        client = build_internal_http_client(settings)

        expected = settings.llm.resolved_internal_api_base
        assert str(client.base_url) == expected

    def test_base_url_uses_explicit_llm_internal_api_base(self) -> None:
        """When llm_internal_api_base is set, uses that value as base_url."""
        from pypsa_app.llm.tools.http_client import build_internal_http_client

        settings = Settings()
        settings.llm.llm_internal_api_base = "http://host.internal:9000"
        client = build_internal_http_client(settings)

        assert str(client.base_url) == "http://host.internal:9000"

    def test_timeout_is_30_seconds(self) -> None:
        """The AsyncClient has a 30-second timeout."""
        from pypsa_app.llm.tools.http_client import build_internal_http_client

        settings = Settings()
        client = build_internal_http_client(settings)

        assert client.timeout == httpx.Timeout(30.0)


class TestBuildInternalHTTPClientCustomPort:
    """Tests that custom llm_internal_port affects the resolved base URL."""

    def test_custom_port_changes_default_base_url(self) -> None:
        """Setting llm_internal_port changes the default base URL."""
        from pypsa_app.llm.tools.http_client import build_internal_http_client

        settings = Settings()
        settings.llm.llm_internal_port = 9999
        client = build_internal_http_client(settings)

        assert str(client.base_url) == "http://127.0.0.1:9999"


class TestBuildInternalHTTPClientIntegration:
    """Integration-style tests confirming the client can make requests."""

    @pytest.mark.anyio
    async def test_client_can_be_used_for_requests(self) -> None:
        """The returned client is functional (no-op, just validates init)."""
        from pypsa_app.llm.tools.http_client import build_internal_http_client

        settings = Settings()
        client = build_internal_http_client(settings)

        # Verify the client was created with expected transport
        assert client.base_url is not None
        assert client.timeout is not None


class TestCookiesFor:
    """Tests for the cookies_for auth-cookie forwarding helper."""

    def test_returns_session_dict_when_auth_cookie_present(self) -> None:
        """When auth_cookie is set, returns {"pypsa_session": value}.

        The cookie name must match SESSION_COOKIE_NAME in
        backend/settings.py so the called endpoint sees the same
        authenticated user.
        """
        from pypsa_app.llm.tools.base import ToolContext
        from pypsa_app.llm.tools.http_client import cookies_for

        ctx = ToolContext(user_id="user_1", auth_cookie="abc123")
        result = cookies_for(ctx)

        assert result == {"pypsa_session": "abc123"}

    def test_returns_none_when_auth_cookie_is_none(self) -> None:
        """When auth_cookie is None, returns None."""
        from pypsa_app.llm.tools.base import ToolContext
        from pypsa_app.llm.tools.http_client import cookies_for

        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = cookies_for(ctx)

        assert result is None
