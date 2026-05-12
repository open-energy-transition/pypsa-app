"""Tests for GetNetworkDetailTool — retrieves a single network by id."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pypsa_app.llm.tools.base import ToolContext


class TestGetNetworkDetailToolInvoke:
    """Tests that GetNetworkDetailTool calls GET /api/v1/networks/{id}
    and returns a well-shaped payload."""

    @pytest.fixture
    def mock_http(self) -> AsyncMock:
        """Return a mocked httpx.AsyncClient whose get() returns a network."""
        http = AsyncMock(spec=httpx.AsyncClient)

        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "name": "my-grid",
            "filename": "my-grid.nc",
            "file_size": 1234567,
            "file_hash": "sha256:abc123",
            "created_at": "2026-01-15T10:30:00Z",
            "dimensions_count": {"snapshots": 8760},
            "components_count": {"Bus": 100, "Generator": 20},
            "meta": {"crs": "EPSG:4326"},
            "facets": None,
            "visibility": "private",
            "owner": {
                "id": "owner-uuid",
                "username": "alice",
                "email": "alice@example.com",
                "is_approved": True,
                "is_admin": False,
                "created_at": "2025-01-01T00:00:00Z",
            },
            "tags": None,
            "source_run_id": None,
            "update_history": None,
        }
        http.get.return_value = response
        return http

    @pytest.fixture
    def ctx(self) -> ToolContext:
        """Return a ToolContext with an auth cookie set."""
        return ToolContext(user_id="user_1", auth_cookie="session_abc")

    @pytest.mark.anyio
    async def test_invoke_calls_correct_endpoint(
        self, mock_http: AsyncMock, ctx: ToolContext
    ) -> None:
        """The tool must call GET /api/v1/networks/{network_id}."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        tool = GetNetworkDetailTool(http=mock_http)
        network_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        await tool.invoke({"network_id": network_id}, ctx)

        mock_http.get.assert_called_once()
        call_args = mock_http.get.call_args
        assert call_args[0][0] == f"/api/v1/networks/{network_id}"

    @pytest.mark.anyio
    async def test_invoke_forwards_auth_cookie(
        self, mock_http: AsyncMock, ctx: ToolContext
    ) -> None:
        """The tool must forward the auth cookie on the internal HTTP call."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        tool = GetNetworkDetailTool(http=mock_http)
        await tool.invoke(
            {"network_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}, ctx
        )

        call_kwargs = mock_http.get.call_args[1]
        assert "cookies" in call_kwargs
        assert call_kwargs["cookies"] == {"pypsa_session": "session_abc"}

    @pytest.mark.anyio
    async def test_invoke_no_cookie_when_none(
        self, mock_http: AsyncMock
    ) -> None:
        """When auth_cookie is None, cookies must not be passed."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        tool = GetNetworkDetailTool(http=mock_http)
        ctx_no_cookie = ToolContext(user_id="user_1", auth_cookie=None)
        await tool.invoke(
            {"network_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}, ctx_no_cookie
        )

        call_kwargs = mock_http.get.call_args[1]
        assert call_kwargs.get("cookies") is None

    @pytest.mark.anyio
    async def test_invoke_returns_success_result_with_summary(
        self, mock_http: AsyncMock, ctx: ToolContext
    ) -> None:
        """The tool must return a ToolResult with summary and data.

        The summary string mentions the network name, file name, ownership
        relative to the requesting user, and a per-component count snippet.
        """
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        tool = GetNetworkDetailTool(http=mock_http)
        result = await tool.invoke(
            {"network_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}, ctx
        )

        assert result.is_error is False
        assert result.error is None
        assert result.payload is not None

        # Payload must have summary and data
        assert "summary" in result.payload
        assert "data" in result.payload
        assert "network" in result.payload["data"]
        assert "my-grid" in result.payload["summary"]
        # ctx.user_id="user_1" doesn't match owner.id="owner-uuid"
        assert "owned by another user" in result.payload["summary"]

    @pytest.mark.anyio
    async def test_invoke_payload_contains_network_fields(
        self, mock_http: AsyncMock, ctx: ToolContext
    ) -> None:
        """The slim network data in the payload mirrors a curated subset of
        REST response fields. The full ``meta`` blob is intentionally
        replaced by ``meta_summary`` (size + key list) and the full
        ``owner`` object is collapsed to ``is_owner`` to keep the
        context-window cost small."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        tool = GetNetworkDetailTool(http=mock_http)
        result = await tool.invoke(
            {"network_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}, ctx
        )

        network = result.payload["data"]["network"]  # type: ignore[index]
        assert network["id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert network["name"] == "my-grid"
        assert network["filename"] == "my-grid.nc"
        assert network["file_size_bytes"] == 1234567
        assert network["components_count"] == {"Bus": 100, "Generator": 20}
        assert network["dimensions_count"] == {"snapshots": 8760}
        # ctx.user_id="user_1" != owner.id="owner-uuid"
        assert network["is_owner"] is False
        assert network["meta_summary"]["keys"] == ["crs"]
        assert network["meta_summary"]["size_bytes"] > 0

    @pytest.mark.anyio
    async def test_invoke_handles_http_error(
        self, ctx: ToolContext
    ) -> None:
        """When the HTTP call fails, the registry catches it as an error."""
        from pypsa_app.llm.tools import ToolRegistry
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        request = httpx.Request("GET", "http://internal/api/v1/networks/99")
        response = httpx.Response(status_code=404, text="Not found", request=request)
        mock_http.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=request, response=response
        )

        tool = GetNetworkDetailTool(http=mock_http)
        registry = ToolRegistry([tool])
        result = await registry.invoke("get_network_detail", {"network_id": "99"}, ctx)

        assert result.is_error is True
        assert result.payload is None
        assert result.error is not None
        assert "404" in result.error

    @pytest.mark.anyio
    async def test_invoke_handles_unexpected_error(
        self, ctx: ToolContext
    ) -> None:
        """When the HTTP call raises unexpectedly, the registry catches it."""
        from pypsa_app.llm.tools import ToolRegistry
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.side_effect = RuntimeError("connection refused")

        tool = GetNetworkDetailTool(http=mock_http)
        registry = ToolRegistry([tool])
        result = await registry.invoke(
            "get_network_detail",
            {"network_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
            ctx,
        )

        assert result.is_error is True
        assert result.payload is None
        assert result.error is not None
        assert "connection refused" in result.error

    def test_tool_has_correct_class_attributes(self) -> None:
        """The tool must have name, description, and parameters_schema set."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        assert GetNetworkDetailTool.name == "get_network_detail"
        assert isinstance(GetNetworkDetailTool.description, str)
        assert len(GetNetworkDetailTool.description) > 0
        assert "parameters_schema" in GetNetworkDetailTool.__dict__
        schema = GetNetworkDetailTool.parameters_schema
        assert schema["type"] == "object"
        assert "network_id" in schema["properties"]

    def test_tool_to_openai_returns_valid_schema(self) -> None:
        """to_openai() must return a valid OpenAI function-tool schema."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        tool = GetNetworkDetailTool(http=mock_http)
        openai_schema = tool.to_openai()

        assert openai_schema["type"] == "function"
        func = openai_schema["function"]
        assert func["name"] == "get_network_detail"
        assert "network" in func["description"].lower()
        assert func["parameters"]["type"] == "object"
        assert "network_id" in func["parameters"]["properties"]
        assert "network_id" in func["parameters"]["required"]


class TestGetNetworkDetailToolSSR:
    """Tests usable in module-level contexts (no event loop needed)."""

    def test_instantiation_does_not_require_event_loop(self) -> None:
        """Creating a GetNetworkDetailTool must not require a running event loop."""
        from pypsa_app.llm.tools.get_network_detail import GetNetworkDetailTool

        mock_http = MagicMock(spec=httpx.AsyncClient)
        tool = GetNetworkDetailTool(http=mock_http)
        assert tool.name == "get_network_detail"
