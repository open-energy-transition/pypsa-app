"""Tests for the tool-use loop, error envelope, and soft-stop behavior."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from pypsa_app.llm import chat as chat_module
from pypsa_app.llm import tools as tools_pkg
from pypsa_app.llm.schemas import ChatRequest
from pypsa_app.llm.tools import Tool
from tests.conftest import (
    FakeAnthropicClient,
    FakeMessage,
    FakeTextBlock,
    FakeToolUseBlock,
)


def _install_fake_tools(monkeypatch, handler):
    """Replace the real REGISTRY with a single controllable tool."""
    fake_tool = Tool(
        name="fake_tool",
        description="Test tool",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )
    monkeypatch.setattr(tools_pkg, "REGISTRY", {"fake_tool": fake_tool})
    monkeypatch.setattr(chat_module, "REGISTRY", {"fake_tool": fake_tool})


def _install_fake_client(monkeypatch, responses):
    client = FakeAnthropicClient(responses)
    monkeypatch.setattr(chat_module, "_build_client", lambda: client)
    return client


async def test_no_tool_use_returns_text(monkeypatch, fake_user):
    _install_fake_tools(monkeypatch, lambda **_: {})
    client = _install_fake_client(
        monkeypatch,
        [
            FakeMessage(
                content=[FakeTextBlock(text="Hello!")],
                stop_reason="end_turn",
                model="fake-model",
            )
        ],
    )
    response = await chat_module.chat(
        req=ChatRequest(message="hi"), user=fake_user, db=MagicMock()
    )
    assert response.reply == "Hello!"
    assert response.truncated is False
    assert len(client.calls) == 1


async def test_tool_use_cycle_executes_and_returns_text(monkeypatch, fake_user):
    tool_inputs: list[dict[str, Any]] = []

    def handler(**kwargs: Any) -> dict[str, Any]:
        tool_inputs.append(kwargs)
        return {"ok": True}

    _install_fake_tools(monkeypatch, handler)
    client = _install_fake_client(
        monkeypatch,
        [
            FakeMessage(
                content=[
                    FakeToolUseBlock(id="t1", name="fake_tool", input={"x": 1}),
                ],
                stop_reason="tool_use",
            ),
            FakeMessage(
                content=[FakeTextBlock(text="Done.")],
                stop_reason="end_turn",
            ),
        ],
    )
    response = await chat_module.chat(
        req=ChatRequest(message="run tool"),
        user=fake_user,
        db=MagicMock(),
    )
    assert response.reply == "Done."
    assert response.truncated is False
    assert len(client.calls) == 2
    assert len(tool_inputs) == 1
    assert tool_inputs[0]["user"] is fake_user
    assert tool_inputs[0]["x"] == 1
    second_call_messages = client.calls[1]["messages"]
    tool_result_block = next(
        b
        for m in second_call_messages
        if isinstance(m.get("content"), list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_result"
    )
    assert tool_result_block["is_error"] is False
    assert json.loads(tool_result_block["content"]) == {"ok": True}


async def test_tool_error_is_surfaced_as_is_error_block(monkeypatch, fake_user):
    def broken_handler(**_: Any) -> dict:
        raise RuntimeError("db down")

    _install_fake_tools(monkeypatch, broken_handler)
    client = _install_fake_client(
        monkeypatch,
        [
            FakeMessage(
                content=[FakeToolUseBlock(id="t1", name="fake_tool", input={})],
                stop_reason="tool_use",
            ),
            FakeMessage(
                content=[FakeTextBlock(text="Something went wrong, sorry.")],
                stop_reason="end_turn",
            ),
        ],
    )
    response = await chat_module.chat(
        req=ChatRequest(message="call broken"),
        user=fake_user,
        db=MagicMock(),
    )
    assert response.reply == "Something went wrong, sorry."
    tool_result_block = next(
        b
        for m in client.calls[1]["messages"]
        if isinstance(m.get("content"), list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_result"
    )
    assert tool_result_block["is_error"] is True
    assert "RuntimeError" in tool_result_block["content"]


async def test_unknown_tool_is_surfaced_as_is_error(monkeypatch, fake_user):
    monkeypatch.setattr(tools_pkg, "REGISTRY", {})
    monkeypatch.setattr(chat_module, "REGISTRY", {})
    client = _install_fake_client(
        monkeypatch,
        [
            FakeMessage(
                content=[FakeToolUseBlock(id="t1", name="missing", input={})],
                stop_reason="tool_use",
            ),
            FakeMessage(
                content=[FakeTextBlock(text="I cannot help with that right now.")],
                stop_reason="end_turn",
            ),
        ],
    )
    await chat_module.chat(
        req=ChatRequest(message="call missing"),
        user=fake_user,
        db=MagicMock(),
    )
    tool_result_block = next(
        b
        for m in client.calls[1]["messages"]
        if isinstance(m.get("content"), list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_result"
    )
    assert tool_result_block["is_error"] is True
    assert "Unknown tool" in tool_result_block["content"]


async def test_soft_stop_triggers_when_cap_hit(monkeypatch, fake_user):
    monkeypatch.setattr(
        "pypsa_app.backend.settings.settings.llm_max_tool_iterations", 1
    )

    def handler(**_: Any) -> dict:
        return {"ok": True}

    _install_fake_tools(monkeypatch, handler)
    client = _install_fake_client(
        monkeypatch,
        [
            FakeMessage(
                content=[FakeToolUseBlock(id="t1", name="fake_tool", input={})],
                stop_reason="tool_use",
            ),
            FakeMessage(
                content=[FakeTextBlock(text="Stopped early. Say continue.")],
                stop_reason="end_turn",
            ),
        ],
    )
    response = await chat_module.chat(
        req=ChatRequest(message="keep calling"),
        user=fake_user,
        db=MagicMock(),
    )
    assert response.truncated is True
    assert response.reply == "Stopped early. Say continue."
    assert len(client.calls) == 2
    assert "tools" not in client.calls[1]
    last_msg = client.calls[1]["messages"][-1]
    nudge_block = next(b for b in last_msg["content"] if b.get("type") == "text")
    assert "maximum" in nudge_block["text"].lower()
    assert "continue" in nudge_block["text"].lower()


async def test_loop_does_not_trigger_soft_stop_on_end_turn(monkeypatch, fake_user):
    monkeypatch.setattr(
        "pypsa_app.backend.settings.settings.llm_max_tool_iterations", 1
    )

    def handler(**_: Any) -> dict:
        return {"ok": True}

    _install_fake_tools(monkeypatch, handler)
    _install_fake_client(
        monkeypatch,
        [
            FakeMessage(
                content=[FakeTextBlock(text="Hello.")],
                stop_reason="end_turn",
            ),
        ],
    )
    response = await chat_module.chat(
        req=ChatRequest(message="hi"), user=fake_user, db=MagicMock()
    )
    assert response.truncated is False
    assert response.reply == "Hello."
