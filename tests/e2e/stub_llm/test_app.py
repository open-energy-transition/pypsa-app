"""Tests for the stub-LLM FastAPI app."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.e2e.stub_llm.app import app


def test_main_module_imports() -> None:
    """The __main__ module imports successfully (compile-time check)."""
    from tests.e2e.stub_llm import __main__  # noqa: F401

    assert __main__ is not None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_endpoint_returns_200() -> None:
    """The /health endpoint returns 200 OK."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_chat_completions_returns_sse_content_type() -> None:
    """POST /v1/chat/completions with stream=true returns text/event-stream."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/event-stream" in content_type


@pytest.mark.anyio
async def test_chat_completions_has_proper_sse_headers() -> None:
    """SSE response includes Cache-Control, X-Accel-Buffering, Connection headers."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

    assert "no-cache" in response.headers.get("cache-control", "")
    assert response.headers.get("x-accel-buffering") == "no"
    assert response.headers.get("connection") == "keep-alive"


@pytest.mark.anyio
async def test_chat_completions_returns_valid_sse_blocks() -> None:
    """Each line of the SSE response is a valid data: block or [DONE]."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

    body = response.text
    lines = [ln for ln in body.split("\n") if ln.startswith("data:")]

    assert len(lines) >= 1, f"Expected at least 1 data: line, got {lines}"
    for line in lines:
        content = line.removeprefix("data:").strip()
        if content == "[DONE]":
            continue
        # Must be valid JSON
        parsed = json.loads(content)
        assert "choices" in parsed, f"Expected 'choices' in chunk: {parsed}"


@pytest.mark.anyio
async def test_chat_completions_ends_with_done_sentinel() -> None:
    """The SSE stream terminates with data: [DONE]."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

    body = response.text
    assert "data: [DONE]" in body


@pytest.mark.anyio
async def test_chat_completions_produces_content_delta() -> None:
    """At least one chunk contains a content delta for the assistant response."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

    body = response.text
    content_found = False
    for line in body.split("\n"):
        if not line.startswith("data:"):
            continue
        content = line.removeprefix("data:").strip()
        if content == "[DONE]":
            continue
        chunk = json.loads(content)
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            if "content" in delta and delta["content"]:
                content_found = True
                break

    assert content_found, "Expected at least one chunk with content delta"


# --- Tool-call support ---


@pytest.mark.anyio
async def test_list_networks_prompt_returns_tool_call_chunks() -> None:
    """When the user prompt contains 'list networks', SSE chunks include tool_calls."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "list networks"}],
                "stream": True,
            },
        )

    body = response.text
    tool_call_found = False
    tool_call_id_found = False
    for line in body.split("\n"):
        if not line.startswith("data:"):
            continue
        content = line.removeprefix("data:").strip()
        if content == "[DONE]":
            continue
        chunk = json.loads(content)
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            if "tool_calls" in delta and delta["tool_calls"]:
                tool_call_found = True
                tc = delta["tool_calls"][0]
                assert "function" in tc, f"Expected 'function' in tool_call: {tc}"
                # First chunk carries id, type, and function.name
                if "id" in tc:
                    tool_call_id_found = True
                    tc_type_ok = tc.get("type") == "function"
                    assert tc_type_ok, f"Expected type='function': {tc}"
                    assert "name" in tc["function"], f"Expected function.name: {tc}"
                    tc_name_ok = tc["function"]["name"] == "list_networks"
                    assert tc_name_ok, f"Expected list_networks: {tc}"

    assert tool_call_found, "Expected at least one chunk with tool_calls"
    assert tool_call_id_found, "Expected first tool_call chunk to carry id + name"


@pytest.mark.anyio
async def test_list_networks_stream_ends_with_finish_reason_tool_calls(
) -> None:
    """Final SSE chunk has finish_reason='tool_calls' for 'list networks'."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "list networks"}],
                "stream": True,
            },
        )

    body = response.text
    chunks = []
    for line in body.split("\n"):
        if not line.startswith("data:"):
            continue
        content = line.removeprefix("data:").strip()
        if content == "[DONE]":
            continue
        chunks.append(json.loads(content))

    assert chunks, "Expected at least one chunk"
    final = chunks[-1]
    final_reason = final["choices"][0].get("finish_reason")
    assert final_reason == "tool_calls", f"Expected tool_calls, got {final_reason}"


@pytest.mark.anyio
async def test_list_networks_non_streaming_returns_tool_call_message() -> None:
    """Non-streaming request for 'list networks' returns a message with tool_calls."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "list networks"}],
                "stream": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    choice = data["choices"][0]
    assert "message" in choice
    assert "tool_calls" in choice["message"]
    tc = choice["message"]["tool_calls"][0]
    assert tc["function"]["name"] == "list_networks"
    assert choice["finish_reason"] == "tool_calls"


@pytest.mark.anyio
async def test_regular_prompt_still_returns_content() -> None:
    """A prompt without 'list networks' still returns content (not tool calls)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Say hello"}],
                "stream": True,
            },
        )

    body = response.text
    has_content = False
    has_tool_calls = False
    for line in body.split("\n"):
        if not line.startswith("data:"):
            continue
        content = line.removeprefix("data:").strip()
        if content == "[DONE]":
            continue
        chunk = json.loads(content)
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            if "content" in delta and delta["content"]:
                has_content = True
            if "tool_calls" in delta and delta["tool_calls"]:
                has_tool_calls = True

    assert has_content, "Expected content delta for non-tool prompt"
    assert not has_tool_calls, "Expected no tool_calls for non-tool prompt"


@pytest.mark.anyio
async def test_stream_false_returns_json_response() -> None:
    """POST /v1/chat/completions with stream=false returns a JSON response."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
        )

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) >= 1
    assert "message" in data["choices"][0]
