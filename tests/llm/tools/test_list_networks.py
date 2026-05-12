"""Tests for ListNetworksTool — GET /api/v1/networks, payload reshape."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from pypsa_app.llm.tools.base import ToolContext, ToolResult


class TestListNetworksTool:
    """Tests for ListNetworksTool invoking the /api/v1/networks endpoint."""

    def test_name_is_list_networks(self) -> None:
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = httpx.AsyncClient()
        tool = ListNetworksTool(http)
        assert tool.name == "list_networks"

    def test_description_is_non_empty(self) -> None:
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = httpx.AsyncClient()
        tool = ListNetworksTool(http)
        assert len(tool.description) > 0

    def test_parameters_schema_has_limit(self) -> None:
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = httpx.AsyncClient()
        tool = ListNetworksTool(http)
        assert "limit" in tool.parameters_schema.get("properties", {})

    def test_to_openai_returns_function_schema(self) -> None:
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = httpx.AsyncClient()
        tool = ListNetworksTool(http)
        schema = tool.to_openai()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "list_networks"

    @pytest.mark.anyio
    async def test_invoke_calls_get_with_correct_params(self) -> None:
        """invoke() calls GET /api/v1/networks/ with limit, skip, sort_by,
        and order. The trailing slash matches the FastAPI router on
        backend/api/routes/networks.py:105 (NetworkListResponse)."""
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "net_1",
                    "name": "Alpha",
                    "visibility": "private",
                    "owner": {"id": "user_1"},
                    "created_at": "2026-01-01",
                },
                {
                    "id": "net_2",
                    "name": "Beta",
                    "visibility": "public",
                    "owner": {"id": "user_2"},
                    "created_at": "2026-01-02",
                },
            ],
            "meta": {"total": 2},
        }
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        await tool.invoke({"limit": 10}, ctx)

        http.get.assert_called_once_with(
            "/api/v1/networks/",
            params={
                "limit": 10,
                "skip": 0,
                "sort_by": "created_at",
                "order": "desc",
            },
            cookies=None,
        )

    @pytest.mark.anyio
    async def test_invoke_defaults_limit_to_25(self) -> None:
        """When limit is not provided, defaults to 25."""
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [], "meta": {"total": 0}}
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        await tool.invoke({}, ctx)

        http.get.assert_called_once_with(
            "/api/v1/networks/",
            params={
                "limit": 25,
                "skip": 0,
                "sort_by": "created_at",
                "order": "desc",
            },
            cookies=None,
        )

    @pytest.mark.anyio
    async def test_invoke_forwards_auth_cookie(self) -> None:
        """When ctx.auth_cookie is set, forwards it via cookies_for as
        {pypsa_session: <cookie>} matching SESSION_COOKIE_NAME."""
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [], "meta": {"total": 0}}
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie="session=abc123")
        await tool.invoke({"limit": 5}, ctx)

        http.get.assert_called_once_with(
            "/api/v1/networks/",
            params={
                "limit": 5,
                "skip": 0,
                "sort_by": "created_at",
                "order": "desc",
            },
            cookies={"pypsa_session": "session=abc123"},
        )

    @pytest.mark.anyio
    async def test_result_payload_shape_includes_summary_data_display_hint(
        self,
    ) -> None:
        """On success the payload has summary, data, and display_hint keys."""
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "n1",
                    "name": "Network 1",
                    "visibility": "public",
                    "owner": {"id": "alice"},
                    "created_at": "2026-05-01T10:00:00Z",
                },
            ],
            "meta": {"total": 1},
        }
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await tool.invoke({"limit": 25}, ctx)

        assert isinstance(result, ToolResult)
        assert result.is_error is False
        assert result.payload is not None
        assert "summary" in result.payload
        assert "data" in result.payload
        assert "display_hint" in result.payload
        assert result.payload["display_hint"] == "table"

    @pytest.mark.anyio
    async def test_rows_reshape_correctly(self) -> None:
        """Each row is [id, name, visibility, is_owner, modified].

        is_owner is derived by comparing owner.id to ctx.user_id; modified
        falls back to created_at when update_history is empty/absent."""
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "n1",
                    "name": "Grid A",
                    "visibility": "private",
                    "owner": {"id": "user_1"},
                    "created_at": "2026-01-01",
                },
                {
                    "id": "n2",
                    "name": "Grid B",
                    "visibility": "public",
                    "owner": {"id": "bob"},
                    "created_at": "2026-02-01",
                },
            ],
            "meta": {"total": 2},
        }
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await tool.invoke({}, ctx)

        assert result.payload is not None
        data = result.payload["data"]
        assert data["columns"] == [
            "id",
            "name",
            "visibility",
            "is_owner",
            "modified",
        ]
        assert data["rows"] == [
            ["n1", "Grid A", "private", True, "2026-01-01"],
            ["n2", "Grid B", "public", False, "2026-02-01"],
        ]

    @pytest.mark.anyio
    async def test_summary_reflects_row_count_and_limit(self) -> None:
        """The summary message reports the network count and pagination
        position in the form 'Found N networks (showing X-Y of Z).'"""
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": f"n{i}",
                    "name": "X",
                    "visibility": "private",
                    "owner": {"id": "u1"},
                    "created_at": "2026-01-01",
                }
                for i in range(3)
            ],
            "meta": {"total": 3},
        }
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await tool.invoke({"limit": 50}, ctx)

        assert result.payload is not None
        assert "3 networks" in result.payload["summary"]
        assert "showing 1-3 of 3" in result.payload["summary"]

    @pytest.mark.anyio
    async def test_raise_for_status_propagates_http_errors(self) -> None:
        """HTTP errors cause raise_for_status() to throw, caught by registry."""
        import httpx

        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 500
        # Set up raise_for_status to actually raise
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=httpx.Request("GET", "http://internal/api/v1/networks"),
            response=httpx.Response(
                status_code=500, text="boom", request=httpx.Request("GET", "/")
            ),
        )
        http.get.return_value = mock_response

        tool = ListNetworksTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)

        with pytest.raises(httpx.HTTPStatusError):
            await tool.invoke({}, ctx)

    def test_tool_is_subclass_of_tool_abc(self) -> None:
        from pypsa_app.llm.tools.base import Tool
        from pypsa_app.llm.tools.list_networks import ListNetworksTool

        http = httpx.AsyncClient()
        tool = ListNetworksTool(http)
        assert isinstance(tool, Tool)
