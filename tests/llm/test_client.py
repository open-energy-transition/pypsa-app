"""Tests for LLMClient — LiteLLM streaming wrapper."""

from __future__ import annotations

from typing import Any

import pytest

from pypsa_app.llm.client import LLMClient
from pypsa_app.llm.settings import LLMSettings


class _FakeStream:
    """Minimal async iterable that yields pre-canned chunks."""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks: list[dict[str, Any]] = list(chunks)

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> dict[str, Any]:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


@pytest.fixture
def default_settings() -> LLMSettings:
    """LLMSettings with the default openai/qwen3.5:9b configured."""
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"
    return settings


@pytest.fixture
def sample_messages() -> list[dict[str, str]]:
    """Minimal message list representing a single user turn."""
    return [{"role": "user", "content": "hello"}]


@pytest.mark.anyio
async def test_stream_passes_model_string_to_litellm(
    default_settings: LLMSettings,
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must compose the model from settings.model_string."""
    captured_kwargs: dict[str, Any] = {}

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([{"choices": [{"delta": {"content": "hi"}}]}])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(default_settings)
    chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert len(chunks) == 1
    assert captured_kwargs["model"] == "openai/qwen3.5:9b"


@pytest.mark.anyio
async def test_stream_passes_api_base_to_litellm_when_set(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must forward llm_api_base to litellm when configured."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_api_base = "http://localhost:11434/v1"

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert captured_kwargs["api_base"] == "http://localhost:11434/v1"


@pytest.mark.anyio
async def test_stream_passes_api_key_to_litellm_when_set(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must forward llm_api_key to litellm when configured."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_api_key = "sk-test-key"

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert captured_kwargs["api_key"] == "sk-test-key"


@pytest.mark.anyio
async def test_stream_omits_api_key_when_empty(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must NOT include api_key in kwargs when it is empty."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_api_key = ""

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert "api_key" not in captured_kwargs


@pytest.mark.anyio
async def test_stream_omits_api_base_when_none(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must NOT include api_base in kwargs when it is None."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_api_base = None

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert "api_base" not in captured_kwargs


@pytest.mark.anyio
async def test_stream_passes_max_tokens_to_litellm(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must forward llm_max_tokens to litellm."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_max_tokens = 4096

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert captured_kwargs["max_tokens"] == 4096


@pytest.mark.anyio
async def test_stream_passes_temperature_to_litellm(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must forward llm_temperature to litellm."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_temperature = 0.7

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert captured_kwargs["temperature"] == 0.7


@pytest.mark.anyio
async def test_stream_passes_timeout_to_litellm(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must forward llm_request_timeout_seconds to litellm."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_request_timeout_seconds = 60.0

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert captured_kwargs["timeout"] == 60.0


@pytest.mark.anyio
async def test_stream_always_sets_stream_true(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must always pass stream=True to litellm."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert captured_kwargs["stream"] is True


@pytest.mark.anyio
async def test_stream_omits_tools_when_none(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must NOT include tools in kwargs when tools is None."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert "tools" not in captured_kwargs


@pytest.mark.anyio
async def test_stream_includes_tools_when_provided(
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must include tools in kwargs when explicitly provided."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"
    tools = [{"type": "function", "function": {"name": "test_tool"}}]

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        captured_kwargs.update(kwargs)
        return _FakeStream([])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(sample_messages, tools=tools)]

    assert captured_kwargs["tools"] == tools


@pytest.mark.anyio
async def test_stream_yields_chunks_from_litellm(
    default_settings: LLMSettings,
    sample_messages: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream() must yield every chunk returned by litellm.acompletion."""
    chunk1 = {"choices": [{"delta": {"content": "Hello"}}]}
    chunk2 = {"choices": [{"delta": {"content": " world"}}]}

    async def fake_acompletion(**kwargs: Any) -> _FakeStream:
        return _FakeStream([chunk1, chunk2])

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(default_settings)
    chunks = [chunk async for chunk in client.stream(sample_messages)]

    assert len(chunks) == 2
    assert chunks[0] == chunk1
    assert chunks[1] == chunk2


@pytest.mark.anyio
async def test_health_returns_ok_and_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """health() must return {"ok": True, "model": …} on a successful provider ping.

    health() pings the provider with a 1-token completion and returns a
    status dict on success. Errors from the provider must propagate to
    the caller.
    """
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"

    captured_kwargs: dict[str, Any] = {}

    async def fake_acompletion(**kwargs: Any) -> None:
        captured_kwargs.update(kwargs)
        return None

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    result = await client.health()

    assert result == {"ok": True, "model": "openai/qwen3.5:9b"}
    assert captured_kwargs["model"] == "openai/qwen3.5:9b"
    assert captured_kwargs["messages"] == [{"role": "user", "content": "ping"}]
    assert captured_kwargs["max_tokens"] == 1
    assert "stream" not in captured_kwargs


@pytest.mark.anyio
async def test_health_propagates_provider_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """health() must let provider exceptions bubble up to the caller."""
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"

    async def fake_acompletion(**kwargs: Any) -> None:
        msg = "provider connection refused"
        raise ConnectionError(msg)

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    with pytest.raises(ConnectionError, match="provider connection refused"):
        await client.health()


@pytest.mark.anyio
async def test_health_passes_api_key_and_base_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """health() must forward llm_api_key and llm_api_base when configured."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"
    settings.llm_api_key = "sk-test"
    settings.llm_api_base = "http://localhost:11434/v1"

    async def fake_acompletion(**kwargs: Any) -> None:
        captured_kwargs.update(kwargs)
        return None

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    await client.health()

    assert captured_kwargs["api_key"] == "sk-test"
    assert captured_kwargs["api_base"] == "http://localhost:11434/v1"


@pytest.mark.anyio
async def test_health_omits_api_key_and_base_when_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """health() must NOT include api_key or api_base when they are empty/unset."""
    captured_kwargs: dict[str, Any] = {}
    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"
    settings.llm_api_key = ""
    settings.llm_api_base = None

    async def fake_acompletion(**kwargs: Any) -> None:
        captured_kwargs.update(kwargs)
        return None

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    client = LLMClient(settings)
    await client.health()

    assert "api_key" not in captured_kwargs
    assert "api_base" not in captured_kwargs


# ── extract_reasoning / extract_text helpers ──────────────────────


def test_extract_reasoning_picks_thinking_over_reasoning_content() -> None:
    """extract_reasoning must prefer 'thinking' (Anthropic) over 'reasoning_content'."""
    from pypsa_app.llm.client import extract_reasoning

    delta = _Delta(thinking="anthropic thinks", reasoning_content="ollama thinks")
    result = extract_reasoning(delta)

    assert result == "anthropic thinks"


def test_extract_reasoning_falls_back_to_reasoning_content_when_no_thinking() -> None:
    """extract_reasoning must use 'reasoning_content' when 'thinking' is absent."""
    from pypsa_app.llm.client import extract_reasoning

    delta = _Delta(reasoning_content="ollama thinks")
    result = extract_reasoning(delta)

    assert result == "ollama thinks"


def test_extract_reasoning_returns_empty_string_when_neither_field_exists() -> None:
    """extract_reasoning must return '' when neither
    'thinking' nor 'reasoning_content' exists."""
    from pypsa_app.llm.client import extract_reasoning

    delta = _Delta()
    result = extract_reasoning(delta)

    assert result == ""


def test_extract_text_returns_content_when_present() -> None:
    """extract_text must return delta.content when the attribute exists."""
    from pypsa_app.llm.client import extract_text

    delta = _Delta(content="hello world")
    result = extract_text(delta)

    assert result == "hello world"


def test_extract_text_returns_empty_string_when_no_content() -> None:
    """extract_text must return '' when the delta has no 'content' attribute."""
    from pypsa_app.llm.client import extract_text

    delta = _Delta()
    result = extract_text(delta)

    assert result == ""


class _Delta:
    """Minimal delta-like object for testing reasoning/text extraction."""

    def __init__(self, **kwargs: str) -> None:
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


@pytest.mark.anyio
async def test_stream_kwargs_flow_end_to_end_with_and_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full kwargs contract: tools present when provided, absent when omitted.

    LLMClient.stream() must pass tools through to litellm.acompletion
    when explicitly provided and omit the key otherwise.
    """
    messages: list[dict[str, str]] = [{"role": "user", "content": "hello"}]
    tools: list[dict[str, Any]] = [
        {"type": "function", "function": {"name": "test_tool", "parameters": {}}}
    ]

    settings = LLMSettings()
    settings.llm_provider = "openai"
    settings.llm_model = "qwen3.5:9b"

    import litellm

    # ── with tools ──────────────────────────────────────────────────
    captured_with: dict[str, Any] = {}

    async def fake_with(**kwargs: Any) -> _FakeStream:
        captured_with.update(kwargs)
        return _FakeStream([])

    monkeypatch.setattr(litellm, "acompletion", fake_with)

    client = LLMClient(settings)
    _chunks = [chunk async for chunk in client.stream(messages, tools=tools)]

    assert captured_with["tools"] == tools
    assert captured_with["model"] == "openai/qwen3.5:9b"
    assert captured_with["messages"] == messages
    assert captured_with["stream"] is True

    # ── without tools ───────────────────────────────────────────────
    captured_without: dict[str, Any] = {}

    async def fake_without(**kwargs: Any) -> _FakeStream:
        captured_without.update(kwargs)
        return _FakeStream([])

    monkeypatch.setattr(litellm, "acompletion", fake_without)

    _chunks = [chunk async for chunk in client.stream(messages)]

    assert "tools" not in captured_without
    assert captured_without["model"] == "openai/qwen3.5:9b"
    assert captured_without["messages"] == messages
    assert captured_without["stream"] is True
