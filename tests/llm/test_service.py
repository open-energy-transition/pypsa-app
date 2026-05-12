"""Tests for ChatService — skeleton + text-streaming deltas."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pypsa_app.llm.api.schemas import ChatContext, ChatMessage
from pypsa_app.llm.client import LLMClient
from pypsa_app.llm.service import ChatService
from pypsa_app.llm.settings import LLMSettings
from pypsa_app.llm.tools import ToolRegistry


def _parse_sse_events(raw: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Parse SSE bytes into a list of (event_name, payload) tuples."""
    text = raw.decode("utf-8")
    blocks = text.strip().split("\n\n")
    events: list[tuple[str, dict[str, Any]]] = []
    for block in blocks:
        if not block:
            continue
        lines = block.strip().split("\n")
        event_line = lines[0]
        event_name = event_line.removeprefix("event: ")
        data_line = next(ln for ln in lines if ln.startswith("data:"))
        payload = json.loads(data_line.removeprefix("data: "))
        events.append((event_name, payload))
    return events


class TestChatServiceToolCallResult:
    """Focused ToolCallResult tests.

    Verifies that after ToolCallEnd the service invokes the tool via
    the registry and emits ToolCallResult with the result payload.
    The registry is stubbed so the contract is tested in isolation.
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def stubbed_registry(self) -> MagicMock:
        """Stub the ToolRegistry so invoke returns a known payload."""
        from pypsa_app.llm.tools.base import ToolResult

        registry = MagicMock(spec=ToolRegistry)
        registry.schemas = MagicMock(return_value=[])
        registry.invoke = AsyncMock(
            return_value=ToolResult(
                payload={
                    "summary": "ok",
                    "data": {"columns": [], "rows": []},
                    "display_hint": "table",
                }
            )
        )
        return registry

    async def _collect_events(
        self,
        settings: LLMSettings,
        stubbed_registry: MagicMock,
        fake_stream: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="list networks",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client,
            tools=stubbed_registry,
            settings=settings,
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_emits_tool_call_result_with_payload_from_registry(
        self, settings: LLMSettings, stubbed_registry: MagicMock
    ) -> None:
        """When a tool call completes, ToolCallResult must carry the
        result payload from the registry with is_error=False.

        After ToolCallEnd, the service invokes the tool via the registry
        and emits ToolCallResult with result=result.payload.
        """
        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":10}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(
            settings, stubbed_registry, fake_stream
        )

        # Must find a ToolCallResult with is_error=False
        result_events = [
            e for e in events if e[0] == "ToolCallResult"
        ]
        assert len(result_events) == 1, (
            f"Expected exactly 1 ToolCallResult, got {len(result_events)}"
        )

        result_payload = result_events[0][1]
        assert result_payload["tool_call_id"] == "call_42"
        assert result_payload["is_error"] is False
        assert result_payload["result"] == {
            "summary": "ok",
            "data": {"columns": [], "rows": []},
            "display_hint": "table",
        }

    @pytest.mark.anyio
    async def test_registry_invoke_called_with_correct_args(
        self, settings: LLMSettings, stubbed_registry: MagicMock
    ) -> None:
        """The service must call registry.invoke with the tool name,
        parsed arguments, and a ToolContext for the authenticated user.
        """
        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_99",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":50}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        await self._collect_events(
            settings, stubbed_registry, fake_stream
        )

        # Registry.invoke must have been called once
        stubbed_registry.invoke.assert_awaited_once()

        # Verify the args passed to invoke
        call_args = stubbed_registry.invoke.call_args
        assert call_args is not None
        args, kwargs = call_args
        assert args[0] == "list_networks"
        assert args[1] == {"limit": 50}

        # The third arg is a ToolContext
        ctx = args[2]
        assert ctx.user_id == "user-1"


class TestChatServiceAuthCookieForwarding:
    """Verify auth_cookie from run_chat is forwarded into ToolContext.

    The route extracts the session cookie from the incoming request and
    passes it through ChatService.run_chat → ToolContext. Tools receive
    that cookie so they can forward it on internal HTTP calls.
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def stubbed_registry(self) -> MagicMock:
        from pypsa_app.llm.tools.base import ToolResult

        registry = MagicMock(spec=ToolRegistry)
        registry.schemas = MagicMock(return_value=[])
        registry.invoke = AsyncMock(
            return_value=ToolResult(
                payload={
                    "summary": "ok",
                    "data": {"columns": [], "rows": []},
                    "display_hint": "table",
                }
            )
        )
        return registry

    @pytest.mark.anyio
    async def test_auth_cookie_forwarded_to_tool_context(
        self, settings: LLMSettings, stubbed_registry: MagicMock
    ) -> None:
        """When run_chat receives auth_cookie, the ToolContext passed
        to registry.invoke must carry that same auth_cookie.
        """
        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":10}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="list networks",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client,
            tools=stubbed_registry,
            settings=settings,
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
                auth_cookie="session_abc123",
            )
        ]

        # Consume stream
        _ = b"".join(chunks)

        # Registry.invoke must have been called
        stubbed_registry.invoke.assert_awaited_once()
        call_args = stubbed_registry.invoke.call_args
        assert call_args is not None
        args, _kwargs = call_args
        ctx = args[2]
        assert ctx.user_id == "user-1"
        assert ctx.auth_cookie == "session_abc123", (
            f"Expected auth_cookie='session_abc123' in ToolContext, "
            f"got {ctx.auth_cookie!r}"
        )

    @pytest.mark.anyio
    async def test_auth_cookie_none_when_not_provided(
        self, settings: LLMSettings, stubbed_registry: MagicMock
    ) -> None:
        """When run_chat is called without auth_cookie (or None),
        the ToolContext.auth_cookie must be None."""
        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_1",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":5}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="list networks",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client,
            tools=stubbed_registry,
            settings=settings,
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        _ = b"".join(chunks)

        stubbed_registry.invoke.assert_awaited_once()
        call_args = stubbed_registry.invoke.call_args
        assert call_args is not None
        args, _kwargs = call_args
        ctx = args[2]
        assert ctx.user_id == "user-1"
        assert ctx.auth_cookie is None, (
            f"Expected auth_cookie=None in ToolContext, "
            f"got {ctx.auth_cookie!r}"
        )


class TestChatServiceSkeleton:
    """Verify the ChatService skeleton emits RunStarted → RunFinished."""

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def client(self, settings: LLMSettings) -> MagicMock:
        mock = MagicMock(spec=LLMClient)
        mock._s = settings

        async def _empty_stream(
            messages: object, tools: object = None
        ) -> Any:
            if False:  # never yields — empty stream
                yield

        mock.stream = _empty_stream
        return mock

    @pytest.fixture
    def tools(self) -> MagicMock:
        return MagicMock(spec=ToolRegistry)

    @pytest.fixture
    def service(
        self, client: MagicMock, tools: MagicMock, settings: LLMSettings
    ) -> ChatService:
        return ChatService(client=client, tools=tools, settings=settings)

    @pytest.mark.anyio
    async def test_service_importable(self) -> None:
        """ChatService must be importable from pypsa_app.llm.service."""
        assert ChatService is not None

    async def _collect_events(
        self, service: ChatService
    ) -> list[tuple[str, dict[str, Any]]]:
        """Run chat with a single "Hi" message and return parsed SSE events."""
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hi",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]
        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_run_chat_emits_run_started_then_run_finished(
        self, service: ChatService
    ) -> None:
        """The skeleton must emit exactly RunStarted then RunFinished SSE events."""
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hello",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        assert len(chunks) >= 2

        combined = b"".join(chunks)
        events = _parse_sse_events(combined)

        assert len(events) == 2
        assert events[0][0] == "RunStarted"
        assert events[1][0] == "RunFinished"

    @pytest.mark.anyio
    async def test_run_started_has_valid_run_id_and_model(
        self, service: ChatService
    ) -> None:
        """RunStarted must contain a non-empty run_id and the model string."""
        events = await self._collect_events(service)
        run_started = events[0][1]

        assert run_started["run_id"].startswith("run_")
        assert len(run_started["run_id"]) > 4
        assert run_started["model"] == "openai/qwen3.5:9b"

    @pytest.mark.anyio
    async def test_run_finished_has_same_run_id_stop_reason(
        self, service: ChatService
    ) -> None:
        """RunFinished must have same run_id as RunStarted and end_turn stop_reason."""
        events = await self._collect_events(service)
        run_started = events[0][1]
        run_finished = events[1][1]

        assert run_finished["run_id"] == run_started["run_id"]
        assert run_finished["stop_reason"] == "end_turn"
        assert run_finished["usage"]["input_tokens"] == 0
        assert run_finished["usage"]["output_tokens"] == 0

    @pytest.mark.anyio
    async def test_unique_run_id_per_call(self, service: ChatService) -> None:
        """Each call to run_chat must produce a unique run_id."""

        async def get_run_id() -> str:
            events = await self._collect_events(service)
            return str(events[0][1]["run_id"])

        run_id_1 = await get_run_id()
        run_id_2 = await get_run_id()

        assert run_id_1 != run_id_2

    @pytest.mark.anyio
    async def test_health_delegates_to_client(
        self, service: ChatService, client: MagicMock
    ) -> None:
        """health() must delegate to the LLMClient.health() method."""
        expected: dict[str, object] = {"ok": True, "model": "openai/qwen3.5:9b"}
        client.health = AsyncMock(return_value=expected)

        result = await service.health()

        assert result == expected
        client.health.assert_awaited_once()

    @pytest.mark.anyio
    async def test_sse_bytes_use_to_sse_format(
        self, service: ChatService
    ) -> None:
        """Each SSE block must use compact JSON (no spaces within data payload)."""
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hi",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        combined = b"".join(chunks)
        text = combined.decode("utf-8")
        for block in text.strip().split("\n\n"):
            data_line = next(
                ln for ln in block.split("\n") if ln.startswith("data:")
            )
            json_part = data_line[5:].strip()
            # Compact JSON: no spaces
            assert " " not in json_part

    @pytest.mark.anyio
    async def test_run_chat_streams_text_deltas_from_llm(
        self, settings: LLMSettings, tools: MagicMock
    ) -> None:
        """run_chat must stream TextMessageContent deltas between
        RunStarted and RunFinished.

        The service iterates over LLMClient.stream() chunks, extracts
        delta.content, and yields TextMessageContent SSE events. All
        deltas share a single per-assistant-message message_id.
        """
        messages_history = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hi",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        # Fake LLMClient.stream() yielding three content chunks
        async def fake_stream(
            messages: object, tools: object = None
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="Hel")
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="lo")
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=" world")
                    )
                ]
            )

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages_history,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        events = _parse_sse_events(b"".join(chunks))

        # Event sequence: RunStarted → 3×TextMessageContent → RunFinished
        assert len(events) == 5
        assert events[0][0] == "RunStarted"
        assert events[1][0] == "TextMessageContent"
        assert events[1][1]["delta"] == "Hel"
        assert events[2][0] == "TextMessageContent"
        assert events[2][1]["delta"] == "lo"
        assert events[3][0] == "TextMessageContent"
        assert events[3][1]["delta"] == " world"
        assert events[4][0] == "RunFinished"

        # All TextMessageContent events share the same message_id
        mid: str = events[1][1]["message_id"]
        assert mid
        assert events[2][1]["message_id"] == mid
        assert events[3][1]["message_id"] == mid

    @pytest.mark.anyio
    async def test_run_chat_skips_chunks_with_none_content(
        self, settings: LLMSettings, tools: MagicMock
    ) -> None:
        """run_chat must skip LLM chunks whose delta.content is None."""
        messages_history = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hi",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        async def fake_stream(
            messages: object, tools: object = None
        ) -> Any:
            # First chunk: role-only, content is None
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(delta=SimpleNamespace(content=None))
                ]
            )
            # Second chunk: actual content
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(delta=SimpleNamespace(content="Hi"))
                ]
            )
            # Third chunk: content is missing (no attribute)
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace())]
            )

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages_history,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        events = _parse_sse_events(b"".join(chunks))

        # Only RunStarted, one TextMessageContent, RunFinished
        assert len(events) == 3
        assert events[0][0] == "RunStarted"
        assert events[1][0] == "TextMessageContent"
        assert events[1][1]["delta"] == "Hi"
        assert events[2][0] == "RunFinished"


class TestChatServiceToolCallStreaming:
    """Tool-call streaming: ToolCallStart on first chunk, ToolCallArgs, ToolCallEnd, and ToolCallResult."""

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def tools(self) -> ToolRegistry:
        """Real ToolRegistry with a single fake tool."""
        from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult

        class FakeListTool(Tool):
            name = "list_networks"
            description = "List networks"
            parameters_schema = {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
            }

            async def invoke(
                self, args: dict[str, Any], ctx: ToolContext
            ) -> ToolResult:
                return ToolResult(
                    payload={
                        "summary": "Found 3 networks.",
                        "data": {"columns": ["name"], "rows": [["n1"]]},
                    }
                )

        return ToolRegistry([FakeListTool(MagicMock())])

    async def _collect_events(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        fake_stream: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Run chat with a fake LLM stream and return parsed SSE events."""
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="list my networks",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_emits_tool_call_start_on_first_tool_call_chunk(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """ToolCallStart must be emitted on the first chunk of a new
        tool call, with the tool_call_id and tool_name.

        The service inspects tool_calls in each delta chunk, buffers per
        tool_call_id, and emits ToolCallStart on first appearance.
        """

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            # Chunk 1: first tool call chunk — id is present
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            # Chunk 2: more arguments — id is absent
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="25}",
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            # Chunk 3: tool_calls finish
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="",
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        event_names = [e[0] for e in events]
        assert "ToolCallStart" in event_names, (
            f"Expected ToolCallStart in event stream, got {event_names}"
        )

        # Find the ToolCallStart
        start_event = next(
            e for e in events if e[0] == "ToolCallStart"
        )
        assert start_event[1]["tool_call_id"] == "call_42"
        assert start_event[1]["tool_name"] == "list_networks"

    @pytest.mark.anyio
    async def test_emits_tool_call_args_for_argument_fragments(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """ToolCallArgs must be emitted for each argument fragment delta."""

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="25}",
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="",
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        args_events = [e for e in events if e[0] == "ToolCallArgs"]
        assert len(args_events) >= 2, (
            f"Expected at least 2 ToolCallArgs, got {len(args_events)}"
        )
        assert args_events[0][1]["tool_call_id"] == "call_42"
        assert args_events[0][1]["delta"] == '{"limit":'
        assert args_events[1][1]["tool_call_id"] == "call_42"
        assert args_events[1][1]["delta"] == "25}"

    @pytest.mark.anyio
    async def test_emits_tool_call_end_and_result_on_finish_tool_calls(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When finish_reason is 'tool_calls', ToolCallEnd and
        ToolCallResult must be emitted for each completed tool call."""

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":25}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        event_names = [e[0] for e in events]
        # Expected sequence: RunStarted, ToolCallStart, ToolCallArgs,
        # ToolCallEnd, ToolCallResult (then possibly RunFinished)
        assert "ToolCallEnd" in event_names, (
            f"Expected ToolCallEnd in event stream, got {event_names}"
        )
        assert "ToolCallResult" in event_names, (
            f"Expected ToolCallResult in event stream, got {event_names}"
        )

        end_event = next(
            e for e in events if e[0] == "ToolCallEnd"
        )
        assert end_event[1]["tool_call_id"] == "call_42"
        assert end_event[1]["args"] == {"limit": 25}

        result_event = next(
            e for e in events if e[0] == "ToolCallResult"
        )
        assert result_event[1]["tool_call_id"] == "call_42"
        assert result_event[1]["is_error"] is False
        assert result_event[1]["result"]["summary"] == "Found 3 networks."

    @pytest.mark.anyio
    async def test_streams_tool_call_args_when_first_chunk_has_no_arguments(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """ToolCallArgs must accumulate and stream argument deltas even
        when the first chunk only carries the call id + name (no args),
        with arguments arriving in subsequent chunks.

        For each tc_delta where function.arguments is non-empty, append
        to the per-call args_str buffer and emit ToolCallArgs with that
        delta.
        """
        called = False

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal called
            if called:
                return
            called = True
            # Chunk 1: starts the call — id + name only, no arguments
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments="",
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            # Chunk 2: first argument fragment
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments='{"limit":',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            # Chunk 3: second argument fragment
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="25}",
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        args_events = [e for e in events if e[0] == "ToolCallArgs"]
        assert len(args_events) == 2, (
            f"Expected exactly 2 ToolCallArgs, got {len(args_events)}"
        )

        assert args_events[0][1]["tool_call_id"] == "call_42"
        assert args_events[0][1]["delta"] == '{"limit":'
        assert args_events[1][1]["tool_call_id"] == "call_42"
        assert args_events[1][1]["delta"] == "25}"

        # Verify ToolCallStart was emitted once (on chunk 1)
        start_events = [e for e in events if e[0] == "ToolCallStart"]
        assert len(start_events) == 1

        # Verify ToolCallEnd + ToolCallResult are emitted after streaming
        end_events = [e for e in events if e[0] == "ToolCallEnd"]
        assert len(end_events) == 1
        assert end_events[0][1]["tool_call_id"] == "call_42"
        assert end_events[0][1]["args"] == {"limit": 25}

        result_events = [e for e in events if e[0] == "ToolCallResult"]
        assert len(result_events) == 1
        assert result_events[0][1]["tool_call_id"] == "call_42"
        assert result_events[0][1]["is_error"] is False

    @pytest.mark.anyio
    async def test_tool_call_start_emitted_only_once_per_tool_call(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """Each tool_call_id must produce exactly one ToolCallStart event."""

        called = False

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal called
            if called:
                # Subsequent calls: return empty to end the tool loop
                return
            called = True
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="25}",
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        start_events = [e for e in events if e[0] == "ToolCallStart"]
        assert len(start_events) == 1, (
            f"Expected exactly 1 ToolCallStart, got {len(start_events)}"
        )

    @pytest.mark.anyio
    async def test_event_ordering_tool_call_start_before_args_before_end(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """Tool-call events must appear in order:
        ToolCallStart → ToolCallArgs* → ToolCallEnd → ToolCallResult."""

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":25}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        idx = {
            name: i
            for i, (name, _) in enumerate(events)
        }
        assert idx.get("ToolCallStart", 999) < idx.get("ToolCallArgs", 0), (
            "ToolCallStart must appear before ToolCallArgs"
        )
        assert idx.get("ToolCallArgs", 999) < idx.get("ToolCallEnd", 0), (
            "ToolCallArgs must appear before ToolCallEnd"
        )
        assert idx.get("ToolCallEnd", 999) < idx.get("ToolCallResult", 0), (
            "ToolCallEnd must appear before ToolCallResult"
        )

    @pytest.mark.anyio
    async def test_invalid_json_args_emits_error_result_and_continues_loop(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When a tool call has invalid JSON arguments, the service must
        emit a ToolCallResult(is_error=True) and still produce a
        consistent conversation history so the tool loop can continue."""

        stream_call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal stream_call_count
            stream_call_count += 1
            if stream_call_count > 1:
                # Second iteration: return a normal text response
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_bad",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments="{invalid json",
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        # Must find a ToolCallResult with is_error=True
        error_results = [
            e
            for e in events
            if e[0] == "ToolCallResult" and e[1].get("is_error")
        ]
        assert len(error_results) == 1, (
            f"Expected 1 error ToolCallResult, got {len(error_results)}"
        )
        assert error_results[0][1]["tool_call_id"] == "call_bad"
        assert "invalid" in error_results[0][1]["error"].lower()

        # ToolCallEnd must NOT be emitted for invalid-JSON calls
        end_events = [e for e in events if e[0] == "ToolCallEnd"]
        assert len(end_events) == 0, (
            f"ToolCallEnd should not be emitted for invalid JSON, "
            f"got {len(end_events)}"
        )

        # The stream must terminate normally (RunFinished), not crash
        final = events[-1]
        assert final[0] == "RunFinished", (
            f"Expected RunFinished as final event, got {final[0]}"
        )

    @pytest.mark.anyio
    async def test_invalid_json_args_includes_decode_error_in_event(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When json.loads raises JSONDecodeError, the ToolCallResult
        error field must include the actual decode error details.

        The error string must follow the pattern ``"invalid json: ..."``
        with the underlying JSONDecodeError message appended.
        """
        stream_call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal stream_call_count
            stream_call_count += 1
            if stream_call_count > 1:
                # Second iteration: LLM responds with text
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="I cannot parse that."
                            ),
                            finish_reason="stop",
                        )
                    ]
                )
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_bad",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments="{not json",
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        # ── error ToolCallResult ──────────────────────────────
        error_results = [
            e
            for e in events
            if e[0] == "ToolCallResult" and e[1].get("is_error")
        ]
        assert len(error_results) == 1, (
            f"Expected 1 error ToolCallResult, got {len(error_results)}"
        )
        error_event = error_results[0][1]
        assert error_event["tool_call_id"] == "call_bad"

        # Error must follow "invalid json: ..." pattern from spec §6.5
        error_msg = error_event["error"]
        assert error_msg is not None
        assert error_msg.startswith("invalid json:"), (
            f"Error must start with 'invalid json:', got '{error_msg}'"
        )
        # Should contain specifics from JSONDecodeError (e.g. line/column)
        assert "Expecting" in error_msg or "line" in error_msg.lower(), (
            f"Error should include decode details, got '{error_msg}'"
        )

        # ── no ToolCallEnd for invalid JSON ───────────────────
        end_events = [e for e in events if e[0] == "ToolCallEnd"]
        assert len(end_events) == 0, (
            f"ToolCallEnd should not be emitted for invalid JSON, "
            f"got {len(end_events)}"
        )

        # ── loop continues: text chunk arrives ────────────────
        text_events = [e for e in events if e[0] == "TextMessageContent"]
        assert len(text_events) >= 1, (
            f"Expected at least 1 text chunk after error, "
            f"got {len(text_events)}"
        )
        assert text_events[0][1]["delta"] == "I cannot parse that."

        # ── RunFinished terminates normally ───────────────────
        final = events[-1]
        assert final[0] == "RunFinished", (
            f"Expected RunFinished as final event, got {final[0]}"
        )
        assert "stop_reason" in final[1]

    @pytest.mark.anyio
    async def test_tool_response_contains_result_not_args(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """The tool-response message appended to openai_messages for
        the next LLM iteration must contain the tool result, not the
        raw arguments string."""

        captured_messages: list[object] = []

        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            # First call: trigger a tool call
            if call_count == 1:
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call_1",
                                        function=SimpleNamespace(
                                            name="list_networks",
                                            arguments='{"limit":10}',
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ]
                )
                return
            # Second call: capture the conversation history
            captured_messages.extend(messages)  # type: ignore[arg-type]
            return

        # We need a stream that the service can call multiple times,
        # but MagicMock doesn't support that easily, so we use a class.
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="list networks",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        # The service ran and produced some output
        assert len(chunks) > 0

        # Verify that the second stream call received the tool result
        # in the tool-message content (not the raw args).
        assert len(captured_messages) >= 3  # user + assistant + tool

        tool_messages = [
            m
            for m in captured_messages
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        assert len(tool_messages) == 1
        content = tool_messages[0]["content"]
        parsed = json.loads(content)
        # Content must be the tool result payload, not the args string
        assert "summary" in parsed, (
            f"Tool response content should contain the result payload, "
            f"got: {content}"
        )
        assert parsed["summary"] == "Found 3 networks."


class TestChatServiceToolCallEnd:
    """Dedicated ToolCallEnd tests.

    ToolCallEnd must be emitted for each completed tool call when
    finish_reason transitions to ``"tool_calls"``. The event carries
    the fully-parsed args from all accumulated argument deltas.
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def tools(self) -> ToolRegistry:
        from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult

        class FakeListTool(Tool):
            name = "list_networks"
            description = "List networks"
            parameters_schema = {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            }

            async def invoke(
                self, args: dict[str, Any], ctx: ToolContext
            ) -> ToolResult:
                return ToolResult(
                    payload={
                        "summary": f"Found {args.get('limit', 0)} networks.",
                        "data": {"columns": ["name"], "rows": [["n1"]]},
                    }
                )

        return ToolRegistry([FakeListTool(MagicMock())])

    async def _collect_events(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        fake_stream: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="list my networks",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_emits_tool_call_end_with_parsed_args_on_finish_reason(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When finish_reason transitions to ``"tool_calls"`` after
        incremental arg streaming, ToolCallEnd must carry the complete
        parsed arguments."""

        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            # Chunk 1: start the call with first fragment
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            # Chunk 2: more args
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments="25}",
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
            # Chunk 3: finish_reason only — no new tool-call data
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        # ToolCallEnd must be present
        end_events = [e for e in events if e[0] == "ToolCallEnd"]
        assert len(end_events) == 1, (
            f"Expected exactly 1 ToolCallEnd, got {len(end_events)}"
        )
        end_payload = end_events[0][1]
        assert end_payload["tool_call_id"] == "call_42"
        # args must be the fully-parsed JSON from all accumulated deltas
        assert end_payload["args"] == {"limit": 25}

        # ToolCallEnd must appear before ToolCallResult
        result_events = [e for e in events if e[0] == "ToolCallResult"]
        assert len(result_events) == 1

        end_idx = next(
            i for i, (name, _) in enumerate(events)
            if name == "ToolCallEnd"
        )
        result_idx = next(
            i for i, (name, _) in enumerate(events)
            if name == "ToolCallResult"
        )
        assert end_idx < result_idx, (
            f"ToolCallEnd (idx {end_idx}) must appear before "
            f"ToolCallResult (idx {result_idx})"
        )

    @pytest.mark.anyio
    async def test_emits_tool_call_end_per_call_on_finish_reason(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """Each completed tool call must receive its own ToolCallEnd
        event when finish_reason is ``"tool_calls"``."""

        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_a",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":3}',
                                    ),
                                ),
                                SimpleNamespace(
                                    index=1,
                                    id="call_b",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":5}',
                                    ),
                                ),
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        end_events = [e for e in events if e[0] == "ToolCallEnd"]
        assert len(end_events) == 2, (
            f"Expected 2 ToolCallEnd events for 2 tool calls, "
            f"got {len(end_events)}"
        )

        end_ids = {e[1]["tool_call_id"] for e in end_events}
        assert end_ids == {"call_a", "call_b"}

        # Each ToolCallEnd must carry its own args
        end_by_id: dict[str, dict[str, Any]] = {
            e[1]["tool_call_id"]: e[1]["args"] for e in end_events
        }
        assert end_by_id["call_a"] == {"limit": 3}
        assert end_by_id["call_b"] == {"limit": 5}

    @pytest.mark.anyio
    async def test_tool_call_end_after_args_before_result(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """The event stream must order tool-call events as:
        ToolCallStart → ToolCallArgs* → ToolCallEnd → ToolCallResult."""

        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_42",
                                    function=SimpleNamespace(
                                        name="list_networks",
                                        arguments='{"limit":25}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        idx: dict[str, int] = {
            name: i for i, (name, _) in enumerate(events)
            if name
            in {"ToolCallStart", "ToolCallArgs", "ToolCallEnd", "ToolCallResult"}
        }

        assert idx.get("ToolCallStart", 999) < idx.get("ToolCallArgs", 0), (
            "ToolCallStart must precede ToolCallArgs"
        )
        assert idx.get("ToolCallArgs", 999) < idx.get("ToolCallEnd", 0), (
            "ToolCallArgs must precede ToolCallEnd"
        )
        assert idx.get("ToolCallEnd", 999) < idx.get("ToolCallResult", 0), (
            "ToolCallEnd must precede ToolCallResult"
        )


class TestChatServiceToolLoopContinue:
    """Tool-loop continuation.

    After ``finish_reason == "tool_calls"`` the service must:
    1. Emit ``ToolCallEnd`` + ``ToolCallResult`` for each tool call
    2. Append assistant tool_calls + tool result messages to the history
    3. Continue the loop — call the LLM again with the updated messages
    4. Stream the LLM's follow-up response (usually a text summary)
    5. Emit ``RunFinished``
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def tools(self) -> ToolRegistry:
        from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult

        class FakeListTool(Tool):
            name = "list_networks"
            description = "List networks"
            parameters_schema = {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            }

            async def invoke(
                self, args: dict[str, Any], ctx: ToolContext
            ) -> ToolResult:
                return ToolResult(
                    payload={
                        "summary": "Found 3 networks.",
                        "data": {"columns": ["name"], "rows": [["n1"]]},
                    }
                )

        return ToolRegistry([FakeListTool(MagicMock())])

    async def _collect_events_for_stream(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        fake_stream: Any,
        messages: list[ChatMessage] | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        if messages is None:
            messages = [
                ChatMessage(
                    id="msg-1",
                    role="user",
                    content="list my networks",
                    timestamp="2026-05-05T10:00:00Z",
                )
            ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_after_tool_call_loop_continues_and_emits_text_then_run_finished(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """After a successful tool call, the service must continue the
        loop, call the LLM again, stream any follow-up text, and emit
        ``RunFinished``.

        Appending the tool message and continuing the loop allows the
        LLM to produce a text summary of the tool result.
        """
        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1

            # First call: LLM decides to call a tool
            if call_count == 1:
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call_42",
                                        function=SimpleNamespace(
                                            name="list_networks",
                                            arguments='{"limit":10}',
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ]
                )
                return

            # Second call: LLM produces a text response about the result
            if call_count == 2:
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="You have 3 "
                            ),
                            finish_reason=None,
                        )
                    ]
                )
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="networks available."
                            ),
                            finish_reason="stop",
                        )
                    ]
                )

        events = await self._collect_events_for_stream(
            settings, tools, fake_stream
        )

        event_names = [e[0] for e in events]

        # The stream must contain RunStarted and RunFinished
        assert "RunStarted" in event_names
        assert "RunFinished" in event_names, (
            f"Expected RunFinished at end, got: {event_names}"
        )

        # Tool call events must be present (first iteration)
        assert "ToolCallStart" in event_names
        assert "ToolCallEnd" in event_names
        assert "ToolCallResult" in event_names

        # Text content from the second LLM call must be present
        assert "TextMessageContent" in event_names, (
            f"Expected TextMessageContent from second LLM call, "
            f"got: {event_names}"
        )

        # Verify event ordering: RunStarted, tool events, then follow-up
        # text from the second LLM call, then RunFinished
        start_idx = next(
            i for i, (n, _) in enumerate(events) if n == "RunStarted"
        )
        tool_result_idx = next(
            i for i, (n, _) in enumerate(events) if n == "ToolCallResult"
        )
        text_idx = next(
            i for i, (n, _) in enumerate(events)
            if n == "TextMessageContent"
        )
        finish_idx = next(
            i for i, (n, _) in enumerate(events) if n == "RunFinished"
        )

        assert start_idx < tool_result_idx < text_idx < finish_idx, (
            "Event ordering mismatch: "
            f"RunStarted({start_idx}) → ToolCallResult({tool_result_idx}) → "
            f"TextMessageContent({text_idx}) → RunFinished({finish_idx})"
        )

        # Verify text content from second call
        text_events = [e for e in events if e[0] == "TextMessageContent"]
        text_parts = "".join(e[1]["delta"] for e in text_events)
        assert text_parts == "You have 3 networks available."

        # RunFinished must have stop_reason from second LLM call
        run_finished = events[-1][1]
        assert run_finished["stop_reason"] == "stop"

    @pytest.mark.anyio
    async def test_second_llm_call_receives_appended_tool_messages(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """The second LLM call must receive the conversation history that
        includes the assistant tool_calls message and the tool result message."""
        captured_messages: list[dict[str, object]] = []
        call_count = 0

        async def fake_stream(
            messages_list: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call_42",
                                        function=SimpleNamespace(
                                            name="list_networks",
                                            arguments='{"limit":10}',
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ]
                )
                return

            if call_count == 2:
                captured_messages.extend(messages_list)  # type: ignore[arg-type]
                return

        await self._collect_events_for_stream(
            settings, tools, fake_stream
        )

        # Should have: user + assistant (tool_calls) + tool (result)
        assert len(captured_messages) >= 3, (
            f"Expected at least 3 messages in second call, "
            f"got {len(captured_messages)}"
        )

        by_role: dict[str, list[dict[str, object]]] = {}
        for msg in captured_messages:
            role = str(msg.get("role", ""))
            by_role.setdefault(role, []).append(msg)

        # Must have exactly one user message
        assert len(by_role.get("user", [])) == 1

        # Must have at least one assistant message with tool_calls
        assistant_msgs = by_role.get("assistant", [])
        assert len(assistant_msgs) >= 1
        assistant_with_tool_calls = [
            m for m in assistant_msgs if m.get("tool_calls")
        ]
        assert len(assistant_with_tool_calls) == 1, (
            f"Expected exactly 1 assistant message with tool_calls, "
            f"got {len(assistant_with_tool_calls)}"
        )

        assistant_msg = assistant_with_tool_calls[0]
        tool_calls = assistant_msg["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_42"
        assert tool_calls[0]["type"] == "function"
        assert tool_calls[0]["function"]["name"] == "list_networks"
        assert tool_calls[0]["function"]["arguments"] == '{"limit":10}'

        # Must have at least one tool message with the result
        tool_msgs = by_role.get("tool", [])
        assert len(tool_msgs) == 1, (
            f"Expected exactly 1 tool message, got {len(tool_msgs)}"
        )
        tool_msg = tool_msgs[0]
        assert tool_msg["tool_call_id"] == "call_42"
        # Tool result must be the serialized payload, not raw args
        content = json.loads(str(tool_msg["content"]))
        assert content["summary"] == "Found 3 networks."

    @pytest.mark.anyio
    async def test_multiple_tool_call_iterations(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """The service must support multiple consecutive tool-call
        iterations in a single chat turn.

        First iteration: tool call → tool runs → messages appended.
        Second iteration: LLM receives appended messages, makes
        another tool call → tool runs → messages appended.
        Third iteration: LLM produces final text response.
        """
        call_count = 0

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First: LLM calls list_networks
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call_1",
                                        function=SimpleNamespace(
                                            name="list_networks",
                                            arguments='{"limit":10}',
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ]
                )
                return

            if call_count == 2:
                # Second: LLM calls list_networks again (with different
                # limit — simulating a follow-up call based on context)
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="Let me check ",
                            ),
                            finish_reason=None,
                        )
                    ]
                )
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call_2",
                                        function=SimpleNamespace(
                                            name="list_networks",
                                            arguments='{"limit":5}',
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ]
                )
                return

            if call_count == 3:
                # Third: LLM gives final summary
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="All done."
                            ),
                            finish_reason="stop",
                        )
                    ]
                )

        events = await self._collect_events_for_stream(
            settings, tools, fake_stream
        )

        # First tool-call iteration events
        result_events = [
            e for e in events if e[0] == "ToolCallResult"
        ]
        assert len(result_events) == 2, (
            f"Expected 2 ToolCallResult events (one per tool iteration), "
            f"got {len(result_events)}"
        )
        assert result_events[0][1]["tool_call_id"] == "call_1"
        assert result_events[1][1]["tool_call_id"] == "call_2"

        # Text from the second and third LLM calls
        text_events = [
            e for e in events if e[0] == "TextMessageContent"
        ]
        assert len(text_events) >= 2

        text_parts = "".join(e[1]["delta"] for e in text_events)
        assert "Let me check" in text_parts
        assert "All done." in text_parts

        # Must end with RunFinished
        assert events[-1][0] == "RunFinished"


class TestChatServiceMaxToolIterations:
    """Max tool-iteration cap.

    When the LLM keeps requesting tool calls beyond the configured
    ``llm_max_tool_iterations``, the service soft-stops with a
    tools-disabled summary call and emits ``RunFinished`` with
    ``stop_reason="tool_iteration_limit"``.
    """

    @pytest.fixture
    def settings_low_cap(self) -> LLMSettings:
        """Settings with max_tool_iterations set to 2."""
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
            llm_max_tool_iterations=2,
        )

    @pytest.fixture
    def stubbed_registry(self) -> ToolRegistry:
        """Registry with a stub tool so the loop can run."""
        from pypsa_app.llm.tools.base import Tool, ToolContext, ToolResult

        class StubTool(Tool):
            name = "stub"
            description = "Stub"
            parameters_schema = {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
            }

            async def invoke(
                self, args: dict[str, Any], ctx: ToolContext
            ) -> ToolResult:
                return ToolResult(payload={"ok": True})

        return ToolRegistry([StubTool(MagicMock())])

    async def _collect_events(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        fake_stream: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="do something with tools",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_soft_stops_with_summary_when_tool_iteration_cap_exceeded(
        self,
        settings_low_cap: LLMSettings,
        stubbed_registry: ToolRegistry,
    ) -> None:
        """When the LLM never produces finish_reason="stop" and tool
        iterations exceed the cap, the service must NOT crash — instead
        it appends a system notice asking the model to wrap up, calls
        _stream_summary with tools disabled, and emits a final
        RunFinished with stop_reason="tool_iteration_limit".
        """

        async def infinite_tool_calls(
            messages: object, **kwargs: object
        ) -> Any:
            # Always return a tool-call request — the LLM never stops.
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_x",
                                    function=SimpleNamespace(
                                        name="stub",
                                        arguments='{"x":1}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )

        events = await self._collect_events(
            settings_low_cap, stubbed_registry, infinite_tool_calls
        )

        # Must contain RunStarted + per-iteration tool events + final
        # RunFinished with stop_reason="tool_iteration_limit".
        assert events[0][0] == "RunStarted"

        assert events[-1][0] == "RunFinished", (
            f"Expected RunFinished as final event, got {events[-1][0]}"
        )

        run_finished = events[-1][1]
        assert run_finished["stop_reason"] == "tool_iteration_limit"
        assert run_finished["run_id"] == events[0][1]["run_id"]

        # No RunError should appear anywhere in the soft-stop path.
        assert not any(name == "RunError" for name, _ in events), (
            f"Soft-stop must not emit RunError; got events: "
            f"{[name for name, _ in events]}"
        )

        # Exactly one RunFinished — the soft-stop one with stop_reason
        # set to tool_iteration_limit.
        finished = [e for e in events if e[0] == "RunFinished"]
        assert len(finished) == 1, (
            f"Expected exactly one RunFinished from the soft-stop path, "
            f"got {len(finished)}"
        )

        # There must be exactly 2 ToolCallResult events (one per iteration
        # with max_tool_iterations=2). The cap is enforced; no extra
        # tool calls happen during _stream_summary because tools=None.
        results = [e for e in events if e[0] == "ToolCallResult"]
        assert len(results) == 2, (
            f"Expected exactly 2 ToolCallResult events "
            f"(max_tool_iterations=2), got {len(results)}"
        )



class TestChatServiceClientDisconnect:
    """Client-disconnect cancellation.

    When ``client_disconnected`` returns ``True`` mid-stream the
    service must:

    1. Log INFO with ``reason=client_disconnect``
    2. Raise ``asyncio.CancelledError``
    3. NOT emit ``RunError`` or ``RunFinished`` after the cancellation
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.mark.anyio
    async def test_cancels_and_no_run_error_when_client_disconnects(
        self, settings: LLMSettings
    ) -> None:
        """When client_disconnected returns True after the second chunk,
        CancelledError must propagate and no RunError or RunFinished
        must be emitted.

        The service polls client_disconnected between chunks, and on
        True raises CancelledError without emitting RunError.
        """
        import asyncio

        async def fake_stream(
            messages: object, tools: object = None
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="Hel")
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="lo")
                    )
                ]
            )
            # Third chunk — must never be emitted because disconnect
            # is detected after the second chunk.
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=" world")
                    )
                ]
            )

        check_count = 0

        async def client_disconnected() -> bool:
            nonlocal check_count
            check_count += 1
            # Return True after the second check (i.e. after the second
            # chunk has been processed).
            return check_count > 1

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        tools = MagicMock(spec=ToolRegistry)
        tools.schemas = MagicMock(return_value=[])

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        user = MagicMock()
        user.id = "user-1"

        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hi",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()

        collected: list[bytes] = []
        try:
            async for sse_bytes in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=client_disconnected,
            ):
                collected.append(sse_bytes)  # noqa: PERF401
            pytest.fail("Expected CancelledError but stream completed")
        except asyncio.CancelledError:
            pass  # expected — client disconnect cancels the stream

        events = _parse_sse_events(b"".join(collected))
        event_names = [e[0] for e in events]

        # Should have RunStarted + exactly 2 TextMessageContent events.
        assert "RunStarted" in event_names, (
            f"Expected RunStarted, got {event_names}"
        )
        text_count = event_names.count("TextMessageContent")
        assert text_count == 2, (
            f"Expected exactly 2 TextMessageContent events, got {text_count}"
        )

        # No RunError, no RunFinished.
        assert "RunError" not in event_names, (
            f"RunError must NOT be emitted on client disconnect, "
            f"got {event_names}"
        )
        assert "RunFinished" not in event_names, (
            f"RunFinished must NOT be emitted on client disconnect, "
            f"got {event_names}"
        )

        # Verify the deltas from the first two chunks only.
        text_events = [
            e for e in events if e[0] == "TextMessageContent"
        ]
        deltas = "".join(e[1]["delta"] for e in text_events)
        assert deltas == "Hello", (
            f"Expected 'Hello' from first two chunks, got '{deltas}'"
        )


class TestChatServiceProviderExceptions:
    """Provider exceptions → RunError.

    When the LLM provider raises an exception during streaming, the
    service must catch it, emit ``RunError`` with an appropriate
    error code and message, and stop without emitting ``RunFinished``.

    Mapping:
    - ``httpx.TimeoutException`` → code="provider_timeout"
    - ``litellm.exceptions.AuthenticationError`` → code="provider_auth_failed"
    - ``litellm.exceptions.RateLimitError`` → code="provider_rate_limit"
    - Anything else (last-resort) → code="internal"
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def tools(self) -> ToolRegistry:
        return MagicMock(spec=ToolRegistry)

    async def _collect_events(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        fake_stream: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="Hi",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_timeout_exception_emits_provider_timeout_run_error(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When the provider raises httpx.TimeoutException, the service
        must emit RunError(code="provider_timeout") and stop.
        """
        import httpx

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            raise httpx.TimeoutException("request timed out")
            yield  # type: ignore[unreachable] — makes this an async generator

        events = await self._collect_events(settings, tools, fake_stream)

        # Must have RunStarted + RunError
        assert events[0][0] == "RunStarted"
        assert events[-1][0] == "RunError", (
            f"Expected RunError as final event, got {events[-1][0]}"
        )

        error_event = events[-1][1]
        assert error_event["code"] == "provider_timeout"
        assert "timed out" in error_event["message"]
        assert error_event["run_id"] == events[0][1]["run_id"]

        # RunFinished must NOT be emitted
        finished = [e for e in events if e[0] == "RunFinished"]
        assert len(finished) == 0, "RunFinished must NOT be emitted on error"

    @pytest.mark.anyio
    async def test_authentication_error_emits_provider_auth_failed_run_error(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When the provider raises litellm AuthenticationError, the
        service must emit RunError(code="provider_auth_failed") and stop.
        """
        import litellm.exceptions

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            raise litellm.exceptions.AuthenticationError(
                message="invalid api key",
                response=MagicMock(),
                llm_provider="openai",
                model="qwen3.5:9b",
            )
            yield  # type: ignore[unreachable]

        events = await self._collect_events(settings, tools, fake_stream)

        assert events[0][0] == "RunStarted"
        assert events[-1][0] == "RunError", (
            f"Expected RunError as final event, got {events[-1][0]}"
        )

        error_event = events[-1][1]
        assert error_event["code"] == "provider_auth_failed"
        assert "invalid api key" in error_event["message"]
        assert error_event["run_id"] == events[0][1]["run_id"]

        finished = [e for e in events if e[0] == "RunFinished"]
        assert len(finished) == 0

    @pytest.mark.anyio
    async def test_rate_limit_error_emits_provider_rate_limit_run_error(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When the provider raises litellm RateLimitError, the service
        must emit RunError(code="provider_rate_limit") and stop.
        """
        import litellm.exceptions

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            raise litellm.exceptions.RateLimitError(
                message="rate limit exceeded",
                response=MagicMock(),
                llm_provider="openai",
                model="qwen3.5:9b",
            )
            yield  # type: ignore[unreachable]

        events = await self._collect_events(settings, tools, fake_stream)

        assert events[0][0] == "RunStarted"
        assert events[-1][0] == "RunError", (
            f"Expected RunError as final event, got {events[-1][0]}"
        )

        error_event = events[-1][1]
        assert error_event["code"] == "provider_rate_limit"
        assert "rate limit" in error_event["message"]
        assert error_event["run_id"] == events[0][1]["run_id"]

        finished = [e for e in events if e[0] == "RunFinished"]
        assert len(finished) == 0

    @pytest.mark.anyio
    async def test_generic_exception_emits_internal_run_error(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When the provider raises an unexpected exception type, the
        service must emit RunError(code="internal") with the exception
        message and stop.
        """

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            msg = "something unexpected broke"
            raise RuntimeError(msg)
            yield  # type: ignore[unreachable]

        events = await self._collect_events(settings, tools, fake_stream)

        assert events[0][0] == "RunStarted"
        assert events[-1][0] == "RunError", (
            f"Expected RunError as final event, got {events[-1][0]}"
        )

        error_event = events[-1][1]
        assert error_event["code"] == "internal"
        assert "unexpected" in error_event["message"]
        assert error_event["run_id"] == events[0][1]["run_id"]

        finished = [e for e in events if e[0] == "RunFinished"]
        assert len(finished) == 0

    @pytest.mark.anyio
    async def test_run_error_emitted_then_stream_ends(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """After a provider exception, the stream must emit RunStarted
        followed by exactly one RunError event and then terminate — no
        extra events.
        """
        import httpx

        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            raise httpx.TimeoutException("timeout")
            yield  # type: ignore[unreachable]

        events = await self._collect_events(settings, tools, fake_stream)

        # Exactly two events: RunStarted and RunError
        assert len(events) == 2, (
            f"Expected exactly 2 events (RunStarted + RunError), "
            f"got {len(events)}"
        )
        assert events[0][0] == "RunStarted"
        assert events[1][0] == "RunError"


class TestChatServiceReasoningMessageContent:
    """ReasoningMessageContent delta streaming.

    The service must normalise reasoning content from provider-specific
    fields (``delta.thinking`` for Anthropic,
    ``delta.reasoning_content`` for Ollama qwen) using the
    ``extract_reasoning`` helper from ``client.py`` and emit
    ``ReasoningMessageContent`` SSE events.
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def tools(self) -> ToolRegistry:
        return MagicMock(spec=ToolRegistry)

    async def _collect_events(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        fake_stream: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        messages = [
            ChatMessage(
                id="msg-1",
                role="user",
                content="think about this",
                timestamp="2026-05-05T10:00:00Z",
            )
        ]
        context = ChatContext()
        user = MagicMock()
        user.id = "user-1"

        mock_client = MagicMock(spec=LLMClient)
        mock_client.stream = fake_stream

        service = ChatService(
            client=mock_client, tools=tools, settings=settings
        )

        chunks = [
            chunk
            async for chunk in service.run_chat(
                user=user,
                messages=messages,
                context=context,
                client_disconnected=lambda: False,
            )
        ]

        return _parse_sse_events(b"".join(chunks))

    @pytest.mark.anyio
    async def test_emits_reasoning_from_thinking_field(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When a delta has a ``thinking`` attribute (Anthropic), the
        service must emit ``ReasoningMessageContent`` with that content.
        extract_reasoning prefers thinking over reasoning_content.
        """
        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            thinking="Hmm, let me reason step by step...",
                            content=None,
                        ),
                        finish_reason=None,
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            thinking="",
                            content="The answer is 42.",
                        ),
                        finish_reason="stop",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        reasoning_events = [
            e for e in events if e[0] == "ReasoningMessageContent"
        ]
        assert len(reasoning_events) >= 1, (
            f"Expected at least 1 ReasoningMessageContent, "
            f"got {len(reasoning_events)}"
        )
        assert reasoning_events[0][1]["delta"] == (
            "Hmm, let me reason step by step..."
        )

    @pytest.mark.anyio
    async def test_emits_reasoning_from_reasoning_content_field(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When a delta has a ``reasoning_content`` attribute
        (Ollama qwen), the service must emit
        ``ReasoningMessageContent`` with that content.
        Falls back to reasoning_content when thinking is absent.
        """
        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            reasoning_content="Let's analyze the network...",
                            content=None,
                        ),
                        finish_reason=None,
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="Analysis complete.",
                        ),
                        finish_reason="stop",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        reasoning_events = [
            e for e in events if e[0] == "ReasoningMessageContent"
        ]
        assert len(reasoning_events) >= 1, (
            f"Expected at least 1 ReasoningMessageContent, "
            f"got {len(reasoning_events)}"
        )
        assert reasoning_events[0][1]["delta"] == (
            "Let's analyze the network..."
        )

    @pytest.mark.anyio
    async def test_no_reasoning_when_no_reasoning_fields(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When a delta has neither ``thinking`` nor
        ``reasoning_content``, no ``ReasoningMessageContent`` event
        must be emitted.
        """
        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="Just a normal response.",
                        ),
                        finish_reason="stop",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        reasoning_events = [
            e for e in events if e[0] == "ReasoningMessageContent"
        ]
        assert len(reasoning_events) == 0, (
            f"Expected 0 ReasoningMessageContent events when delta "
            f"has no reasoning fields, got {len(reasoning_events)}"
        )

    @pytest.mark.anyio
    async def test_reasoning_and_text_can_appear_in_same_chunk(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """When a single delta carries both reasoning content and text
        content, the service must emit both ``ReasoningMessageContent``
        and ``TextMessageContent`` events in the same iteration.
        """
        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            thinking="Reasoning first...",
                            content="Then text.",
                        ),
                        finish_reason="stop",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        event_names = [e[0] for e in events]
        assert "ReasoningMessageContent" in event_names, (
            f"Expected ReasoningMessageContent, got {event_names}"
        )
        assert "TextMessageContent" in event_names, (
            f"Expected TextMessageContent alongside reasoning, "
            f"got {event_names}"
        )

    @pytest.mark.anyio
    async def test_reasoning_shares_message_id_with_text(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """All ``ReasoningMessageContent`` and ``TextMessageContent``
        events within a single assistant message turn must share the
        same ``message_id``.
        """
        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            thinking="Step 1...",
                            content="First part.",
                        ),
                        finish_reason=None,
                    )
                ]
            )
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            thinking="Step 2...",
                            content="Second part.",
                        ),
                        finish_reason="stop",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        content_events = [
            e
            for e in events
            if e[0] in {"ReasoningMessageContent", "TextMessageContent"}
        ]
        assert len(content_events) >= 2, (
            f"Expected at least 2 content events, got {len(content_events)}"
        )

        message_ids = {e[1]["message_id"] for e in content_events}
        assert len(message_ids) == 1, (
            f"All content events must share the same message_id, "
            f"got {message_ids}"
        )

    @pytest.mark.anyio
    async def test_uses_extract_reasoning_for_normalisation(
        self, settings: LLMSettings, tools: ToolRegistry
    ) -> None:
        """The service must consume the ``extract_reasoning`` helper
        from ``client.py`` for reasoning-content normalisation rather
        than duplicating the logic.
        """
        async def fake_stream(
            messages: object, **kwargs: object
        ) -> Any:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            thinking="anthropic reasoning",
                            reasoning_content="ollama reasoning",
                        ),
                        finish_reason="stop",
                    )
                ]
            )

        events = await self._collect_events(settings, tools, fake_stream)

        reasoning_events = [
            e for e in events if e[0] == "ReasoningMessageContent"
        ]
        assert len(reasoning_events) == 1, (
            f"Expected exactly 1 ReasoningMessageContent, "
            f"got {len(reasoning_events)}"
        )
        # extract_reasoning prefers 'thinking' over 'reasoning_content'
        assert reasoning_events[0][1]["delta"] == "anthropic reasoning", (
            f"Expected 'thinking' to take priority, got "
            f"{reasoning_events[0][1]['delta']!r}"
        )


# ── ChatService.health() full-chain tests ──────────────────────────


class TestChatServiceHealth:
    """ChatService.health() full-chain tests.

    Verifies that ChatService.health() truly pings the LLM provider by
    exercising the complete chain:
    ChatService.health() → LLMClient.health() → litellm.acompletion().
    """

    @pytest.fixture
    def settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )

    @pytest.fixture
    def tools(self) -> ToolRegistry:
        return MagicMock(spec=ToolRegistry)

    @pytest.mark.anyio
    async def test_health_pings_provider_with_ping_message(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ChatService.health() must cause litellm.acompletion to be
        called with a 'ping' user message and max_tokens=1.
        """
        captured_kwargs: dict[str, object] = {}

        async def fake_acompletion(**kwargs: object) -> None:
            captured_kwargs.update(kwargs)
            return None

        import litellm

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

        client = LLMClient(settings)
        service = ChatService(client=client, tools=tools, settings=settings)

        result = await service.health()

        assert result == {"ok": True, "model": "openai/qwen3.5:9b"}
        assert captured_kwargs["model"] == "openai/qwen3.5:9b"
        assert captured_kwargs["messages"] == [
            {"role": "user", "content": "ping"}
        ]
        assert captured_kwargs["max_tokens"] == 1

    @pytest.mark.anyio
    async def test_health_passes_api_key_and_base_when_configured(
        self, tools: ToolRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ChatService.health() must forward llm_api_key and
        llm_api_base to litellm through the full chain."""
        captured_kwargs: dict[str, object] = {}
        settings = LLMSettings(
            llm_provider="openai",
            llm_model="qwen3.5:9b",
        )
        settings.llm_api_key = "sk-test"
        settings.llm_api_base = "http://localhost:11434/v1"

        async def fake_acompletion(**kwargs: object) -> None:
            captured_kwargs.update(kwargs)
            return None

        import litellm

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

        client = LLMClient(settings)
        service = ChatService(client=client, tools=tools, settings=settings)

        result = await service.health()

        assert result == {"ok": True, "model": "openai/qwen3.5:9b"}
        assert captured_kwargs["api_key"] == "sk-test"
        assert captured_kwargs["api_base"] == "http://localhost:11434/v1"

    @pytest.mark.anyio
    async def test_health_propagates_provider_exception(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ChatService.health() must let provider exceptions bubble
        up to the caller through the full client chain.
        """
        async def fake_acompletion(**kwargs: object) -> None:
            msg = "provider connection refused"
            raise ConnectionError(msg)

        import litellm

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

        client = LLMClient(settings)
        service = ChatService(client=client, tools=tools, settings=settings)

        with pytest.raises(ConnectionError, match="provider connection refused"):
            await service.health()

    @pytest.mark.anyio
    async def test_health_return_type_conforms_to_contract(
        self,
        settings: LLMSettings,
        tools: ToolRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ChatService.health() must return a dict with exactly
        'ok' (bool) and 'model' (str) keys.
        """
        async def fake_acompletion(**kwargs: object) -> None:
            return None

        import litellm

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

        client = LLMClient(settings)
        service = ChatService(client=client, tools=tools, settings=settings)

        result = await service.health()

        assert isinstance(result, dict)
        assert set(result.keys()) == {"ok", "model"}
        assert result["ok"] is True
        assert isinstance(result["model"], str)
        assert len(result["model"]) > 0
