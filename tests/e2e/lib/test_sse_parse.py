"""Unit tests for tests/e2e/lib/sse_parse.py.

Tests the SSE → JSON-lines parser by feeding SSE block fixtures
via subprocess.run and asserting per-line JSON output matches
expected events.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sse_parse.py"


def _run_sse_parse(input_text: str) -> list[dict]:
    """Run sse_parse.py with the given SSE input, return parsed JSON lines."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=input_text,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(f"[stderr] {result.stderr}", file=sys.stderr)
    lines = result.stdout.strip().split("\n")
    if lines == [""]:
        return []
    return [json.loads(line) for line in lines]


class TestSseParseSingleBlock:
    """Single SSE block parsing."""

    def test_basic_event_is_parsed(self) -> None:
        """A single event:data block produces one JSON line."""
        input_text = (
            "event: TextMessageContent\n"
            'data: {"message_id":"msg_01","delta":"Hello"}\n'
            "\n"
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "TextMessageContent"
        assert events[0]["data"] == {"message_id": "msg_01", "delta": "Hello"}

    def test_multiple_blocks_produce_multiple_outputs(self) -> None:
        """Multiple SSE blocks → multiple JSON lines."""
        input_text = (
            "event: RunStarted\n"
            'data: {"run_id":"r1","model":"openai/qwen3.5:9b"}\n'
            "\n"
            "event: TextMessageContent\n"
            'data: {"message_id":"m1","delta":"Hi"}\n'
            "\n"
            "event: RunFinished\n"
            'data: {"run_id":"r1","usage":{"total_tokens":10},"stop_reason":"stop"}\n'
            "\n"
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 3
        assert events[0]["event"] == "RunStarted"
        assert events[1]["event"] == "TextMessageContent"
        assert events[2]["event"] == "RunFinished"

    def test_comment_lines_are_ignored(self) -> None:
        """SSE comment lines (starting with :) are skipped."""
        input_text = ':keepalive\n\nevent: TextMessageContent\ndata: {"delta":"ok"}\n\n'
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "TextMessageContent"

    def test_block_with_no_event_name_is_skipped(self) -> None:
        """Block with data but no event: line is silently dropped."""
        input_text = (
            'data: {"orphan":true}\n'
            "\n"
            "event: TextMessageContent\n"
            'data: {"delta":"real"}\n'
            "\n"
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "TextMessageContent"

    def test_non_json_data_uses_raw_fallback(self) -> None:
        """Bad JSON in data → _raw fallback."""
        input_text = "event: RunError\ndata: not-valid-json\n\n"
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "RunError"
        assert events[0]["data"] == {"_raw": "not-valid-json"}

    def test_multiline_data_is_accumulated(self) -> None:
        """Multiple data: lines in one block are concatenated."""
        input_text = (
            "event: TextMessageContent\n"
            'data: {"message_id":"m1",\n'
            'data:  "delta":"Hello"}\n'
            "\n"
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "TextMessageContent"
        assert events[0]["data"] == {"message_id": "m1", "delta": "Hello"}

    def test_empty_input_produces_no_output(self) -> None:
        """Empty input → no JSON lines."""
        events = _run_sse_parse("")
        assert events == []

    def test_tool_call_start_event(self) -> None:
        """ToolCallStart event round-trip."""
        input_text = (
            "event: ToolCallStart\n"
            'data: {"tool_call_id":"call_01","tool_name":"list_networks"}\n'
            "\n"
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "ToolCallStart"
        assert events[0]["data"] == {
            "tool_call_id": "call_01",
            "tool_name": "list_networks",
        }

    def test_run_error_event(self) -> None:
        """RunError event round-trip."""
        input_text = (
            "event: RunError\n"
            'data: {"run_id":"r1","code":"PROVIDER_ERROR","message":"timeout"}\n'
            "\n"
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "RunError"
        assert events[0]["data"] == {
            "run_id": "r1",
            "code": "PROVIDER_ERROR",
            "message": "timeout",
        }


class TestSseParseEdgeCases:
    """Edge case and robustness tests."""

    def test_trailing_data_is_flushed(self) -> None:
        """Unterminated last block (no final blank line) is still emitted."""
        input_text = (
            'event: TextMessageContent\ndata: {"delta":"partial"}'
            # no trailing blank line — real SSE may not have one at EOF
        )
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "TextMessageContent"
        assert events[0]["data"] == {"delta": "partial"}

    def test_extra_whitespace_around_event_name(self) -> None:
        """Event: line with extra whitespace still parses correctly."""
        input_text = 'event:   TextMessageContent   \ndata: {"delta":"x"}\n\n'
        events = _run_sse_parse(input_text)

        assert len(events) == 1
        assert events[0]["event"] == "TextMessageContent"
