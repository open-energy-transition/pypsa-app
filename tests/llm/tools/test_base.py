"""Tests for Tool ABC, ToolContext, and ToolResult dataclasses."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import httpx
import pytest

from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult


class _ConcreteTool(Tool):
    """Minimal concrete tool for testing the ABC."""

    name = "test_tool"
    description = "A test tool for unit testing the Tool ABC."
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
        },
    }

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(payload={"echo": args.get("query", "")})


class TestToolContext:
    """Tests for the ToolContext dataclass."""

    def test_constructor_sets_fields_with_auth_cookie(self) -> None:
        ctx = ToolContext(user_id="user_1", auth_cookie="session=abc123")
        assert ctx.user_id == "user_1"
        assert ctx.auth_cookie == "session=abc123"

    def test_constructor_accepts_none_auth_cookie(self) -> None:
        ctx = ToolContext(user_id="user_2", auth_cookie=None)
        assert ctx.user_id == "user_2"
        assert ctx.auth_cookie is None

    def test_frozen_raises_on_field_assignment(self) -> None:
        ctx = ToolContext(user_id="user_1", auth_cookie="cookie")
        with pytest.raises(FrozenInstanceError):
            ctx.user_id = "changed"  # type: ignore[misc]

    def test_frozen_raises_on_auth_cookie_assignment(self) -> None:
        ctx = ToolContext(user_id="user_1", auth_cookie="cookie")
        with pytest.raises(FrozenInstanceError):
            ctx.auth_cookie = "changed"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        a = ToolContext(user_id="u1", auth_cookie="c1")
        b = ToolContext(user_id="u1", auth_cookie="c1")
        assert a == b

    def test_inequality_different_user_id(self) -> None:
        a = ToolContext(user_id="u1", auth_cookie="c1")
        b = ToolContext(user_id="u2", auth_cookie="c1")
        assert a != b


class TestToolResult:
    """Tests for the ToolResult dataclass."""

    def test_constructor_sets_fields_success(self) -> None:
        result = ToolResult(
            payload={"summary": "Found 3 networks", "data": {}},
            is_error=False,
            error=None,
        )
        assert result.payload == {"summary": "Found 3 networks", "data": {}}
        assert result.is_error is False
        assert result.error is None

    def test_constructor_sets_fields_error(self) -> None:
        result = ToolResult(
            payload=None,
            is_error=True,
            error="http 500: internal server error",
        )
        assert result.payload is None
        assert result.is_error is True
        assert result.error == "http 500: internal server error"

    def test_constructor_defaults_is_error_false(self) -> None:
        result = ToolResult(payload={"ok": True})
        assert result.is_error is False

    def test_constructor_defaults_error_none(self) -> None:
        result = ToolResult(payload={"ok": True})
        assert result.error is None

    def test_frozen_raises_on_field_assignment(self) -> None:
        result = ToolResult(payload={"x": 1}, is_error=False, error=None)
        with pytest.raises(FrozenInstanceError):
            result.payload = {"y": 2}  # type: ignore[misc]

    def test_frozen_raises_on_is_error_assignment(self) -> None:
        result = ToolResult(payload=None, is_error=True, error="boom")
        with pytest.raises(FrozenInstanceError):
            result.is_error = False  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        a = ToolResult(payload={"x": 1}, is_error=False, error=None)
        b = ToolResult(payload={"x": 1}, is_error=False, error=None)
        assert a == b

    def test_inequality_different_payload(self) -> None:
        a = ToolResult(payload={"x": 1})
        b = ToolResult(payload={"x": 2})
        assert a != b

    def test_inequality_different_is_error(self) -> None:
        a = ToolResult(payload=None, is_error=True, error="err")
        b = ToolResult(payload=None, is_error=False, error="err")
        assert a != b


class TestTool:
    """Tests for the Tool abstract base class."""

    def test_cannot_instantiate_abstract_class_directly(self) -> None:
        with pytest.raises(
            TypeError,
            match="Can't instantiate abstract class",
        ):
            Tool(http=httpx.AsyncClient())  # type: ignore[abstract]

    def test_cannot_instantiate_subclass_without_invoke(self) -> None:
        """A subclass that doesn't implement invoke stays abstract."""

        class _NoInvokeTool(Tool):
            name = "no_invoke"
            description = "missing invoke"
            parameters_schema: dict[str, Any] = {}

        with pytest.raises(
            TypeError,
            match="Can't instantiate abstract class",
        ):
            _NoInvokeTool(http=httpx.AsyncClient())  # type: ignore[abstract]

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        http = httpx.AsyncClient()
        tool = _ConcreteTool(http)
        assert tool.name == "test_tool"
        assert tool.description == "A test tool for unit testing the Tool ABC."

    def test_concrete_subclass_stores_http_client(self) -> None:
        http = httpx.AsyncClient()
        tool = _ConcreteTool(http)
        assert tool._http is http

    def test_to_openai_returns_correct_function_schema(self) -> None:
        http = httpx.AsyncClient()
        tool = _ConcreteTool(http)
        schema = tool.to_openai()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert schema["function"]["description"] == (
            "A test tool for unit testing the Tool ABC."
        )
        assert schema["function"]["parameters"] == {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        }

    @pytest.mark.anyio
    async def test_invoke_returns_tool_result(self) -> None:
        http = httpx.AsyncClient()
        tool = _ConcreteTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie=None)
        result = await tool.invoke({"query": "hello"}, ctx)
        assert result.payload == {"echo": "hello"}
        assert result.is_error is False

    @pytest.mark.anyio
    async def test_invoke_preserves_context_not_mutated(self) -> None:
        http = httpx.AsyncClient()
        tool = _ConcreteTool(http)
        ctx = ToolContext(user_id="user_1", auth_cookie="secret")
        await tool.invoke({"query": "x"}, ctx)
        assert ctx.user_id == "user_1"
        assert ctx.auth_cookie == "secret"

    def test_to_openai_minimal_empty_parameters_schema(self) -> None:
        """A tool with empty properties produces a valid OpenAI function schema."""

        class _MinimalTool(Tool):
            name = "x"
            description = "d"
            parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}

            async def invoke(
                self, args: dict[str, Any], ctx: ToolContext
            ) -> ToolResult:
                msg = "not called in this test"
                raise NotImplementedError(msg)

        tool = _MinimalTool(http=httpx.AsyncClient())
        schema = tool.to_openai()

        assert schema == {
            "type": "function",
            "function": {
                "name": "x",
                "description": "d",
                "parameters": {"type": "object", "properties": {}},
            },
        }
