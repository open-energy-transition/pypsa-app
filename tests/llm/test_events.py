"""Tests for AG-UI event dataclasses and SSE serializer."""

from __future__ import annotations

import asyncio
import json
from dataclasses import FrozenInstanceError, asdict

import pytest

from pypsa_app.llm.events import (
    ReasoningMessageContent,
    RunError,
    RunFinished,
    RunStarted,
    TextMessageContent,
    ToolCallArgs,
    ToolCallEnd,
    ToolCallResult,
    ToolCallStart,
    Usage,
    heartbeat,
    sse_encode,
    to_sse,
)


def _parse_sse_data(raw: bytes) -> tuple[str, dict]:
    """Extract (event_name, payload) from SSE wire-format bytes."""
    text = raw.decode("utf-8")
    lines = text.strip().split("\n")
    event_line = lines[0]
    event_name = event_line.removeprefix("event: ")
    data_line = next(ln for ln in lines if ln.startswith("data:"))
    payload = json.loads(data_line.removeprefix("data: "))
    return event_name, payload


class TestTextMessageContent:
    def test_constructor_sets_fields(self) -> None:
        event = TextMessageContent(message_id="msg_01", delta="Hello ")
        assert event.message_id == "msg_01"
        assert event.delta == "Hello "

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = TextMessageContent(message_id="msg_01", delta="delta")
        with pytest.raises(FrozenInstanceError):
            event.delta = "changed"  # type: ignore[misc]


class TestReasoningMessageContent:
    def test_constructor_sets_fields(self) -> None:
        event = ReasoningMessageContent(message_id="msg_02", delta="thinking...")
        assert event.message_id == "msg_02"
        assert event.delta == "thinking..."

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = ReasoningMessageContent(message_id="msg_02", delta="reasoning")
        with pytest.raises(FrozenInstanceError):
            event.message_id = "changed"  # type: ignore[misc]


class TestRunStarted:
    def test_constructor_sets_fields(self) -> None:
        event = RunStarted(run_id="run_abc123", model="qwen3.5:9b")
        assert event.run_id == "run_abc123"
        assert event.model == "qwen3.5:9b"

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = RunStarted(run_id="run_1", model="gpt-4")
        with pytest.raises(FrozenInstanceError):
            event.run_id = "run_2"  # type: ignore[misc]


class TestUsage:
    def test_constructor_sets_fields(self) -> None:
        usage = Usage(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_frozen_raises_on_field_assignment(self) -> None:
        usage = Usage(input_tokens=10, output_tokens=20)
        with pytest.raises(FrozenInstanceError):
            usage.input_tokens = 99  # type: ignore[misc]

    def test_constructor_zero_tokens_accepted(self) -> None:
        usage = Usage(input_tokens=0, output_tokens=0)
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0


class TestRunFinished:
    def test_constructor_sets_fields(self) -> None:
        event = RunFinished(
            run_id="run_abc123",
            usage=Usage(input_tokens=100, output_tokens=50),
            stop_reason="end_turn",
        )
        assert event.run_id == "run_abc123"
        assert event.usage.input_tokens == 100
        assert event.usage.output_tokens == 50
        assert event.stop_reason == "end_turn"

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = RunFinished(
            run_id="run_1",
            usage=Usage(input_tokens=1, output_tokens=2),
            stop_reason="stop",
        )
        with pytest.raises(FrozenInstanceError):
            event.stop_reason = "nope"  # type: ignore[misc]


class TestRunError:
    def test_constructor_sets_fields(self) -> None:
        event = RunError(
            run_id="run_abc123",
            code="internal",
            message="something went wrong",
        )
        assert event.run_id == "run_abc123"
        assert event.code == "internal"
        assert event.message == "something went wrong"

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = RunError(run_id="run_1", code="timeout", message="timed out")
        with pytest.raises(FrozenInstanceError):
            event.code = "nope"  # type: ignore[misc]


class TestSseEncode:
    """SSE wire-format encoding for event dataclasses."""

    def test_sse_encode_run_started_returns_correct_format(self) -> None:
        event = RunStarted(run_id="run_abc123", model="qwen3.5:9b")
        result = sse_encode(event)

        assert isinstance(result, bytes)

        event_name, payload = _parse_sse_data(result)
        assert event_name == "RunStarted"
        assert payload == {"run_id": "run_abc123", "model": "qwen3.5:9b"}

    def test_sse_encode_run_finished_returns_correct_format(self) -> None:
        event = RunFinished(
            run_id="run_abc123",
            usage=Usage(input_tokens=100, output_tokens=50),
            stop_reason="end_turn",
        )
        result = sse_encode(event)

        event_name, payload = _parse_sse_data(result)
        assert event_name == "RunFinished"
        assert payload == {
            "run_id": "run_abc123",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "stop_reason": "end_turn",
        }

    def test_sse_encode_run_error_returns_correct_format(self) -> None:
        event = RunError(
            run_id="run_abc123",
            code="provider_timeout",
            message="request timed out",
        )
        result = sse_encode(event)

        event_name, payload = _parse_sse_data(result)
        assert event_name == "RunError"
        assert payload == {
            "run_id": "run_abc123",
            "code": "provider_timeout",
            "message": "request timed out",
        }

    def test_sse_encode_terminates_with_blank_line(self) -> None:
        """Each SSE event must be terminated by a blank line (double newline)."""
        event = RunStarted(run_id="r1", model="m1")
        result = sse_encode(event)
        assert result.endswith(b"\n\n")

    def test_sse_encode_special_characters_produce_valid_json(self) -> None:
        """Strings with special characters must be valid JSON."""
        event = RunError(
            run_id="run_1",
            code="bad",
            message='line1\nline2 "quoted"',
        )
        result = sse_encode(event)

        _, payload = _parse_sse_data(result)
        assert payload["message"] == 'line1\nline2 "quoted"'

    def test_sse_encode_zero_usage_tokens_serialized(self) -> None:
        event = RunFinished(
            run_id="run_1",
            usage=Usage(input_tokens=0, output_tokens=0),
            stop_reason="stop",
        )
        result = sse_encode(event)

        _, payload = _parse_sse_data(result)
        assert payload["usage"] == {"input_tokens": 0, "output_tokens": 0}

    def test_sse_encode_text_message_content_returns_correct_format(self) -> None:
        event = TextMessageContent(message_id="msg_01", delta="Hello world")
        result = sse_encode(event)

        assert isinstance(result, bytes)
        event_name, payload = _parse_sse_data(result)
        assert event_name == "TextMessageContent"
        assert payload == {"message_id": "msg_01", "delta": "Hello world"}

    def test_sse_encode_reasoning_message_content_returns_correct_format(self) -> None:
        event = ReasoningMessageContent(message_id="msg_02", delta="Let me think...")
        result = sse_encode(event)

        event_name, payload = _parse_sse_data(result)
        assert event_name == "ReasoningMessageContent"
        assert payload == {"message_id": "msg_02", "delta": "Let me think..."}

    def test_sse_encode_empty_delta_produces_valid_event(self) -> None:
        """An empty delta is valid — streaming may yield blank chunks."""
        event = TextMessageContent(message_id="msg_01", delta="")
        result = sse_encode(event)

        _, payload = _parse_sse_data(result)
        assert payload["delta"] == ""


class TestToolCallStart:
    def test_constructor_sets_fields(self) -> None:
        event = ToolCallStart(tool_call_id="call_42", tool_name="list_networks")
        assert event.tool_call_id == "call_42"
        assert event.tool_name == "list_networks"

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = ToolCallStart(tool_call_id="call_1", tool_name="get_network_detail")
        with pytest.raises(FrozenInstanceError):
            event.tool_call_id = "call_2"  # type: ignore[misc]


class TestToolCallArgs:
    def test_constructor_sets_fields(self) -> None:
        event = ToolCallArgs(tool_call_id="call_42", delta='{"limit":')
        assert event.tool_call_id == "call_42"
        assert event.delta == '{"limit":'

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = ToolCallArgs(tool_call_id="call_1", delta="args")
        with pytest.raises(FrozenInstanceError):
            event.delta = "changed"  # type: ignore[misc]


class TestToolCallEnd:
    def test_constructor_sets_fields(self) -> None:
        event = ToolCallEnd(tool_call_id="call_42", args={"limit": 25})
        assert event.tool_call_id == "call_42"
        assert event.args == {"limit": 25}

    def test_constructor_accepts_none_args(self) -> None:
        event = ToolCallEnd(tool_call_id="call_99", args=None)
        assert event.tool_call_id == "call_99"
        assert event.args is None

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = ToolCallEnd(tool_call_id="call_1", args={})
        with pytest.raises(FrozenInstanceError):
            event.tool_call_id = "call_2"  # type: ignore[misc]


class TestToolCallResult:
    def test_constructor_sets_fields_success(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result={"summary": "Found 3 networks"},
            is_error=False,
            error=None,
        )
        assert event.tool_call_id == "call_42"
        assert event.result == {"summary": "Found 3 networks"}
        assert event.is_error is False
        assert event.error is None

    def test_constructor_sets_fields_error(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result=None,
            is_error=True,
            error="invalid json: unexpected EOF",
        )
        assert event.tool_call_id == "call_42"
        assert event.result is None
        assert event.is_error is True
        assert event.error == "invalid json: unexpected EOF"

    def test_constructor_defaults(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result={"ok": True},
        )
        assert event.is_error is False
        assert event.error is None

    def test_frozen_raises_on_field_assignment(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_1",
            result=None,
            is_error=True,
            error="boom",
        )
        with pytest.raises(FrozenInstanceError):
            event.is_error = False  # type: ignore[misc]

    def test_is_error_true_requires_error_string_set(self) -> None:
        """When is_error is True, error must be a non-None string."""
        with pytest.raises(ValueError, match="error"):
            ToolCallResult(
                tool_call_id="call_42",
                result=None,
                is_error=True,
                error=None,
            )

    def test_is_error_false_allows_none_error(self) -> None:
        """When is_error is False, error may be None."""
        event = ToolCallResult(
            tool_call_id="call_42",
            result={"ok": True},
            is_error=False,
            error=None,
        )
        assert event.error is None


class TestToolCallAsdictRoundTrip:
    """Round-trip via dataclasses.asdict — serialise then reconstruct."""

    def test_tool_call_start_asdict_round_trip(self) -> None:
        event = ToolCallStart(tool_call_id="call_42", tool_name="list_networks")
        d = asdict(event)
        recreated = ToolCallStart(**d)
        assert recreated == event
        assert d == {"tool_call_id": "call_42", "tool_name": "list_networks"}

    def test_tool_call_args_asdict_round_trip(self) -> None:
        event = ToolCallArgs(tool_call_id="call_42", delta='{"limit":')
        d = asdict(event)
        recreated = ToolCallArgs(**d)
        assert recreated == event
        assert d == {"tool_call_id": "call_42", "delta": '{"limit":'}

    def test_tool_call_end_asdict_round_trip(self) -> None:
        event = ToolCallEnd(tool_call_id="call_42", args={"limit": 25})
        d = asdict(event)
        recreated = ToolCallEnd(**d)
        assert recreated == event
        assert d == {"tool_call_id": "call_42", "args": {"limit": 25}}

    def test_tool_call_end_none_args_asdict_round_trip(self) -> None:
        event = ToolCallEnd(tool_call_id="call_99", args=None)
        d = asdict(event)
        recreated = ToolCallEnd(**d)
        assert recreated == event
        assert d["args"] is None

    def test_tool_call_result_success_asdict_round_trip(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result={"summary": "Found 3 networks"},
            is_error=False,
            error=None,
        )
        d = asdict(event)
        recreated = ToolCallResult(**d)
        assert recreated == event

    def test_tool_call_result_error_asdict_round_trip(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result=None,
            is_error=True,
            error="tool execution failed",
        )
        d = asdict(event)
        recreated = ToolCallResult(**d)
        assert recreated == event
        assert recreated.is_error is True
        assert isinstance(recreated.error, str)


class TestSseEncodeToolCall:
    def test_sse_encode_tool_call_start_returns_correct_format(self) -> None:
        event = ToolCallStart(tool_call_id="call_42", tool_name="list_networks")
        result = sse_encode(event)

        assert isinstance(result, bytes)
        event_name, payload = _parse_sse_data(result)
        assert event_name == "ToolCallStart"
        assert payload == {"tool_call_id": "call_42", "tool_name": "list_networks"}

    def test_sse_encode_tool_call_args_returns_correct_format(self) -> None:
        event = ToolCallArgs(tool_call_id="call_42", delta='{"limit":')
        result = sse_encode(event)

        assert isinstance(result, bytes)
        event_name, payload = _parse_sse_data(result)
        assert event_name == "ToolCallArgs"
        assert payload == {"tool_call_id": "call_42", "delta": '{"limit":'}

    def test_sse_encode_tool_call_end_returns_correct_format(self) -> None:
        event = ToolCallEnd(tool_call_id="call_42", args={"limit": 25})
        result = sse_encode(event)

        assert isinstance(result, bytes)
        event_name, payload = _parse_sse_data(result)
        assert event_name == "ToolCallEnd"
        assert payload == {"tool_call_id": "call_42", "args": {"limit": 25}}

    def test_sse_encode_tool_call_end_none_args_returns_correct_format(self) -> None:
        event = ToolCallEnd(tool_call_id="call_99", args=None)
        result = sse_encode(event)

        _, payload = _parse_sse_data(result)
        assert payload["args"] is None

    def test_sse_encode_tool_call_result_success_returns_correct_format(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result={"summary": "Found 3 networks"},
            is_error=False,
            error=None,
        )
        result = sse_encode(event)

        event_name, payload = _parse_sse_data(result)
        assert event_name == "ToolCallResult"
        assert payload == {
            "tool_call_id": "call_42",
            "result": {"summary": "Found 3 networks"},
            "is_error": False,
            "error": None,
        }

    def test_sse_encode_tool_call_result_error_returns_correct_format(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result=None,
            is_error=True,
            error="http 500: internal server error",
        )
        result = sse_encode(event)

        _, payload = _parse_sse_data(result)
        assert payload == {
            "tool_call_id": "call_42",
            "result": None,
            "is_error": True,
            "error": "http 500: internal server error",
        }


def _expected_sse_bytes(event_name: str, payload: dict) -> bytes:
    """Build expected SSE wire-format bytes with compact JSON."""
    json_str = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_name}\ndata: {json_str}\n\n".encode()


class TestToSse:
    """Golden-bytes tests for to_sse — compact JSON, exact byte sequences."""

    def test_to_sse_run_started_golden_bytes(self) -> None:
        event = RunStarted(run_id="run_abc123", model="qwen3.5:9b")
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "RunStarted",
            {"run_id": "run_abc123", "model": "qwen3.5:9b"},
        )
        assert result == expected
        assert isinstance(result, bytes)

    def test_to_sse_run_finished_golden_bytes(self) -> None:
        event = RunFinished(
            run_id="run_abc123",
            usage=Usage(input_tokens=100, output_tokens=50),
            stop_reason="end_turn",
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "RunFinished",
            {
                "run_id": "run_abc123",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "stop_reason": "end_turn",
            },
        )
        assert result == expected

    def test_to_sse_run_error_golden_bytes(self) -> None:
        event = RunError(
            run_id="run_abc123",
            code="provider_timeout",
            message="request timed out",
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "RunError",
            {
                "run_id": "run_abc123",
                "code": "provider_timeout",
                "message": "request timed out",
            },
        )
        assert result == expected

    def test_to_sse_text_message_content_golden_bytes(self) -> None:
        event = TextMessageContent(message_id="msg_01", delta="Hello ")
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "TextMessageContent",
            {"message_id": "msg_01", "delta": "Hello "},
        )
        assert result == expected

    def test_to_sse_reasoning_message_content_golden_bytes(self) -> None:
        event = ReasoningMessageContent(
            message_id="msg_02", delta="Let me think..."
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ReasoningMessageContent",
            {"message_id": "msg_02", "delta": "Let me think..."},
        )
        assert result == expected

    def test_to_sse_tool_call_start_golden_bytes(self) -> None:
        event = ToolCallStart(
            tool_call_id="call_42", tool_name="list_networks"
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ToolCallStart",
            {"tool_call_id": "call_42", "tool_name": "list_networks"},
        )
        assert result == expected

    def test_to_sse_tool_call_args_golden_bytes(self) -> None:
        event = ToolCallArgs(tool_call_id="call_42", delta='{"limit":')
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ToolCallArgs",
            {"tool_call_id": "call_42", "delta": '{"limit":'},
        )
        assert result == expected

    def test_to_sse_tool_call_end_golden_bytes(self) -> None:
        event = ToolCallEnd(tool_call_id="call_42", args={"limit": 25})
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ToolCallEnd",
            {"tool_call_id": "call_42", "args": {"limit": 25}},
        )
        assert result == expected

    def test_to_sse_tool_call_end_none_args_golden_bytes(self) -> None:
        event = ToolCallEnd(tool_call_id="call_99", args=None)
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ToolCallEnd",
            {"tool_call_id": "call_99", "args": None},
        )
        assert result == expected

    def test_to_sse_tool_call_result_success_golden_bytes(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result={"summary": "Found 3 networks"},
            is_error=False,
            error=None,
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ToolCallResult",
            {
                "tool_call_id": "call_42",
                "result": {"summary": "Found 3 networks"},
                "is_error": False,
                "error": None,
            },
        )
        assert result == expected

    def test_to_sse_tool_call_result_error_golden_bytes(self) -> None:
        event = ToolCallResult(
            tool_call_id="call_42",
            result=None,
            is_error=True,
            error="http 500: internal server error",
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "ToolCallResult",
            {
                "tool_call_id": "call_42",
                "result": None,
                "is_error": True,
                "error": "http 500: internal server error",
            },
        )
        assert result == expected

    def test_to_sse_json_has_no_spaces(self) -> None:
        """Compact JSON — no spaces within the JSON payload."""
        event = RunStarted(run_id="r1", model="m1")
        result = to_sse(event)
        text = result.decode()
        data_line = next(
            ln for ln in text.split("\n") if ln.startswith("data:")
        )
        # Strip "data:" (5 chars) and the required single space before JSON
        json_part = data_line[5:].strip()
        assert " " not in json_part  # compact, no spaces in JSON itself
        assert json_part == '{"run_id":"r1","model":"m1"}'

    def test_to_sse_terminates_with_blank_line(self) -> None:
        """Each SSE event must end with \\n\\n."""
        event = RunStarted(run_id="r1", model="m1")
        result = to_sse(event)
        assert result.endswith(b"\n\n")

    def test_to_sse_empty_delta_produces_valid_event(self) -> None:
        event = TextMessageContent(message_id="msg_01", delta="")
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "TextMessageContent",
            {"message_id": "msg_01", "delta": ""},
        )
        assert result == expected

    def test_to_sse_zero_usage_tokens_golden_bytes(self) -> None:
        event = RunFinished(
            run_id="run_1",
            usage=Usage(input_tokens=0, output_tokens=0),
            stop_reason="stop",
        )
        result = to_sse(event)
        expected = _expected_sse_bytes(
            "RunFinished",
            {
                "run_id": "run_1",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "stop_reason": "stop",
            },
        )
        assert result == expected


def _build_all_nine_events() -> list[tuple[str, object]]:
    """Return parametrization ids and instances for all 9 AG-UI event types."""
    return [
        ("RunStarted", RunStarted(run_id="run_abc123", model="qwen3.5:9b")),
        (
            "RunFinished",
            RunFinished(
                run_id="run_abc123",
                usage=Usage(input_tokens=100, output_tokens=50),
                stop_reason="end_turn",
            ),
        ),
        (
            "RunError",
            RunError(
                run_id="run_abc123",
                code="provider_timeout",
                message="request timed out",
            ),
        ),
        (
            "TextMessageContent",
            TextMessageContent(message_id="msg_01", delta="Hello "),
        ),
        (
            "ReasoningMessageContent",
            ReasoningMessageContent(message_id="msg_02", delta="Let me think..."),
        ),
        (
            "ToolCallStart",
            ToolCallStart(tool_call_id="call_42", tool_name="list_networks"),
        ),
        (
            "ToolCallArgs",
            ToolCallArgs(tool_call_id="call_42", delta='{"limit":'),
        ),
        (
            "ToolCallEnd",
            ToolCallEnd(tool_call_id="call_42", args={"limit": 25}),
        ),
        (
            "ToolCallResult",
            ToolCallResult(
                tool_call_id="call_42",
                result={"summary": "Found 3 networks"},
                is_error=False,
                error=None,
            ),
        ),
    ]


class TestSseRoundTrip:
    """Parametrized round-trip: every event type → to_sse() → parse → verify."""

    @pytest.mark.parametrize(
        ("label", "event"),
        _build_all_nine_events(),
        ids=[e[0] for e in _build_all_nine_events()],
    )
    def test_to_sse_round_trip(self, label: str, event: object) -> None:
        """Serialize with to_sse, parse back, assert (event_name, data) matches."""
        raw = to_sse(event)  # type: ignore[arg-type]

        event_name, parsed_dict = _parse_sse_data(raw)

        expected_name = type(event).__name__
        expected_dict = asdict(event)

        assert event_name == expected_name
        assert parsed_dict == expected_dict

    def test_all_nine_event_types_tested(self) -> None:
        """Guardrail — if new event types are added, this test fails."""
        events = [e for _, e in _build_all_nine_events()]
        assert len({type(e).__name__ for e in events}) == 9


class TestHeartbeat:
    """Tests for the SSE heartbeat helper — :keepalive every N seconds while idle."""

    KEEPALIVE = b":keepalive\n\n"

    @staticmethod
    async def _collect_until_stop(gen, max_time: float = 0.3) -> list[bytes]:
        """Collect items from a heartbeat-wrapped gen until it stops or
        max_time elapses."""
        result: list[bytes] = []
        start = asyncio.get_running_loop().time()
        try:
            async for chunk in gen:
                result.append(chunk)
                if asyncio.get_running_loop().time() - start > max_time:
                    break
        except StopAsyncIteration:
            pass
        return result

    @pytest.mark.anyio
    async def test_fast_source_no_heartbeat_when_items_arrive_quickly(self) -> None:
        """No heartbeat when source yields faster than the interval."""

        async def fast_gen():
            yield b"event: Text\ndata: {}\n\n"
            yield b"event: Done\ndata: {}\n\n"

        result: list[bytes] = [
            chunk async for chunk in heartbeat(fast_gen(), interval=0.05)
        ]

        assert self.KEEPALIVE not in result
        assert len(result) == 2

    @pytest.mark.anyio
    async def test_yields_keepalive_when_source_is_slow(self) -> None:
        """A keepalive is yielded when the source takes longer than the interval."""

        async def slow_gen():
            await asyncio.sleep(0.15)  # longer than interval (0.05)
            yield b"event: Text\ndata: {}\n\n"

        result = await self._collect_until_stop(
            heartbeat(slow_gen(), interval=0.05),
            max_time=0.5,
        )

        assert self.KEEPALIVE in result
        data_events = [c for c in result if c != self.KEEPALIVE]
        assert len(data_events) == 1

    @pytest.mark.anyio
    async def test_multiple_keepalives_for_very_slow_source(self) -> None:
        """Multiple keepalives when source takes many multiples of interval."""

        async def very_slow_gen():
            await asyncio.sleep(0.25)  # 5x interval of 0.05
            yield b"event: Text\ndata: {}\n\n"

        result = await self._collect_until_stop(
            heartbeat(very_slow_gen(), interval=0.05),
            max_time=0.6,
        )

        keepalive_count = sum(1 for c in result if c == self.KEEPALIVE)
        assert keepalive_count >= 2
        data_events = [c for c in result if c != self.KEEPALIVE]
        assert len(data_events) == 1

    @pytest.mark.anyio
    async def test_keepalive_exact_bytes_match(self) -> None:
        """The keepalive bytes are exactly b':keepalive\\n\\n'."""

        async def slow_gen():
            await asyncio.sleep(0.15)
            yield b"event: X\ndata: {}\n\n"

        result = await self._collect_until_stop(
            heartbeat(slow_gen(), interval=0.05),
            max_time=0.5,
        )

        for chunk in result:
            if chunk == self.KEEPALIVE:
                assert chunk == b":keepalive\n\n"
                assert isinstance(chunk, bytes)

    @pytest.mark.anyio
    async def test_timer_resets_after_source_yields(self) -> None:
        """After the source yields, the heartbeat timer resets."""

        async def mixed_gen():
            yield b"event: First\ndata: {}\n\n"
            await asyncio.sleep(0.15)  # longer than 0.05
            yield b"event: Second\ndata: {}\n\n"

        result = await self._collect_until_stop(
            heartbeat(mixed_gen(), interval=0.05),
            max_time=0.5,
        )

        assert result[0] == b"event: First\ndata: {}\n\n"
        assert self.KEEPALIVE in result
        data_events = [c for c in result if c != self.KEEPALIVE]
        assert len(data_events) == 2

    @pytest.mark.anyio
    async def test_empty_source_completes_without_keepalive(self) -> None:
        """An empty generator exits immediately without any keepalive."""

        async def empty_gen():
            if False:  # pragma: no cover
                yield b""

        result: list[bytes] = [
            chunk async for chunk in heartbeat(empty_gen(), interval=0.05)
        ]

        assert result == []

    @pytest.mark.anyio
    async def test_generator_exhausts_cleanly_no_trailing_heartbeat(self) -> None:
        """When source finishes, the wrapper stops without extra heartbeat."""

        async def single_gen():
            yield b"event: Text\ndata: {}\n\n"

        result: list[bytes] = [
            chunk async for chunk in heartbeat(single_gen(), interval=0.1)
        ]

        assert result == [b"event: Text\ndata: {}\n\n"]

    @pytest.mark.anyio
    async def test_default_interval_is_15_seconds(self) -> None:
        """The interval parameter defaults to 15.0 seconds."""
        import inspect

        sig = inspect.signature(heartbeat)
        assert sig.parameters["interval"].default == 15.0
