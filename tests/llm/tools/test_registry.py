"""Tests for ToolRegistry — register, invoke, and unknown-name error."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult


class _SimpleTool(Tool):
    """A tool that echoes back its arguments for testing."""

    name = "simple_tool"
    description = "Echoes arguments back."
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
    }

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(payload={"echo": args.get("value", "")})


class _FailingTool(Tool):
    """A tool that always raises for testing error handling."""

    name = "failing_tool"
    description = "Always fails."
    parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        msg = "simulated tool failure"
        raise RuntimeError(msg)


class TestToolRegistryRegister:
    """Tests that the registry stores registered tools."""

    def test_registry_stores_single_tool(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        tool = _SimpleTool(http=httpx.AsyncClient())
        registry = ToolRegistry([tool])
        schemas = registry.schemas()

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "simple_tool"

    def test_registry_stores_multiple_tools(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        tools = [
            _SimpleTool(http=httpx.AsyncClient()),
            _FailingTool(http=httpx.AsyncClient()),
        ]
        registry = ToolRegistry(tools)
        schemas = registry.schemas()

        assert len(schemas) == 2
        names = {s["function"]["name"] for s in schemas}
        assert names == {"simple_tool", "failing_tool"}
        for s in schemas:
            assert s["type"] == "function"

    def test_schemas_returns_correct_openai_format(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        tool = _SimpleTool(http=httpx.AsyncClient())
        registry = ToolRegistry([tool])
        schemas = registry.schemas()

        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "simple_tool"
        assert schema["function"]["description"] == "Echoes arguments back."
        assert "parameters" in schema["function"]


class TestToolRegistryInvoke:
    """Tests that the registry invokes the correct tool by name."""

    @pytest.mark.anyio
    async def test_invoke_routes_to_correct_tool(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        tool = _SimpleTool(http=httpx.AsyncClient())
        registry = ToolRegistry([tool])
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await registry.invoke("simple_tool", {"value": "hello"}, ctx)

        assert result.is_error is False
        assert result.payload == {"echo": "hello"}


class TestToolRegistryExceptionHandling:
    """Tests that the registry catches tool exceptions and returns error results."""

    @pytest.mark.anyio
    async def test_invoke_returns_error_result_on_tool_exception(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        tool = _FailingTool(http=httpx.AsyncClient())
        registry = ToolRegistry([tool])
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await registry.invoke("failing_tool", {}, ctx)

        assert result.is_error is True
        assert result.payload is None
        assert "simulated tool failure" in result.error


class _HTTPStatusErrorTool(Tool):
    """A tool that raises httpx.HTTPStatusError for testing HTTP error handling."""

    name = "http_error_tool"
    description = "Raises an HTTP status error."
    parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        request = httpx.Request("GET", "http://internal/api/v1/networks/99")
        response = httpx.Response(
            status_code=404,
            text="Network 99 not found",
            request=request,
        )
        raise httpx.HTTPStatusError(
            "Not Found", request=request, response=response
        )


class TestToolRegistryHTTPStatusError:
    """Tests that httpx.HTTPStatusError is caught and formatted per the spec."""

    @pytest.mark.anyio
    async def test_invoke_formats_http_status_error(self) -> None:
        """HTTPStatusError must produce error="http {code}: {body[:200]}"."""
        from pypsa_app.llm.tools import ToolRegistry

        tool = _HTTPStatusErrorTool(http=httpx.AsyncClient())
        registry = ToolRegistry([tool])
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await registry.invoke("http_error_tool", {}, ctx)

        assert result.is_error is True
        assert result.payload is None
        assert result.error is not None
        assert result.error.startswith("http ")
        assert "404" in result.error
        assert "Network 99 not found" in result.error

    @pytest.mark.anyio
    async def test_invoke_truncates_long_http_error_body(self) -> None:
        """HTTPStatusError body longer than 200 chars must be truncated to 200."""
        from pypsa_app.llm.tools import ToolRegistry

        long_body = "x" * 500
        request = httpx.Request("GET", "http://internal/api/v1/broken")
        inner_client = httpx.AsyncClient()

        class _LongBodyErrorTool(Tool):
            name = "long_body_tool"
            description = "Raises with long body."
            parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}

            async def invoke(
                self, args: dict[str, Any], ctx: ToolContext
            ) -> ToolResult:
                response = httpx.Response(
                    status_code=500, text=long_body, request=request
                )
                raise httpx.HTTPStatusError(
                    "Internal Server Error", request=request, response=response
                )

        tool = _LongBodyErrorTool(http=inner_client)
        registry = ToolRegistry([tool])
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await registry.invoke("long_body_tool", {}, ctx)

        assert result.is_error is True
        assert result.error is not None
        # Error message is "http {code}: {text[:200]}" so total should be at most
        # len("http 500: ") + 200 = ~210
        assert len(result.error) <= 215
        assert result.error.startswith("http ")
        assert "500" in result.error


class TestBuildDefaultRegistry:
    """Tests for build_default_registry — wires all three default tools."""

    def test_registry_schemas_returns_three_tools(self) -> None:
        """build_default_registry schemas() must return three entries with
        the correct function.name values."""
        from pypsa_app.llm.tools import build_default_registry

        registry = build_default_registry(http=httpx.AsyncClient())
        schemas = registry.schemas()

        assert len(schemas) == 3
        names = {s["function"]["name"] for s in schemas}
        assert names == {
            "list_networks",
            "get_network_detail",
            "get_network_statistics",
        }
        for s in schemas:
            assert s["type"] == "function"


class TestToolRegistryUnknownName:
    """Tests that invoking an unknown tool name returns an error result."""

    @pytest.mark.anyio
    async def test_unknown_tool_name_returns_error(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        registry = ToolRegistry([])
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await registry.invoke("nonexistent", {}, ctx)

        assert result.is_error is True
        assert result.payload is None
        assert result.error is not None
        assert "nonexistent" in result.error
        assert "unknown tool" in result.error.lower()

    @pytest.mark.anyio
    async def test_unknown_tool_name_in_populated_registry(self) -> None:
        from pypsa_app.llm.tools import ToolRegistry

        tool = _SimpleTool(http=httpx.AsyncClient())
        registry = ToolRegistry([tool])
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await registry.invoke("other_tool", {}, ctx)

        assert result.is_error is True
        assert result.payload is None
        assert "other_tool" in result.error
