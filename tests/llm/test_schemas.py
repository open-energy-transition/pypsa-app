"""Tests for chat API request schemas — ChatMessage, ChatContext, ChatRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pypsa_app.llm.api.schemas import ChatContext, ChatMessage, ChatRequest


class TestChatMessage:
    def test_constructor_all_fields_set(self) -> None:
        msg = ChatMessage(
            id="msg-001",
            role="user",
            content="Hello",
            tool_call_id="tc-1",
            tool_name="list_networks",
            timestamp="2026-05-05T10:00:00Z",
        )
        assert msg.id == "msg-001"
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_call_id == "tc-1"
        assert msg.tool_name == "list_networks"
        assert msg.timestamp == "2026-05-05T10:00:00Z"

    def test_content_omitted_empty_string(self) -> None:
        msg = ChatMessage(
            id="msg-002",
            role="assistant",
            timestamp="2026-05-05T10:00:00Z",
        )
        assert msg.content == ""

    def test_tool_call_id_omitted_none(self) -> None:
        msg = ChatMessage(
            id="msg-003",
            role="user",
            timestamp="2026-05-05T10:00:00Z",
        )
        assert msg.tool_call_id is None

    def test_tool_name_omitted_none(self) -> None:
        msg = ChatMessage(
            id="msg-004",
            role="user",
            timestamp="2026-05-05T10:00:00Z",
        )
        assert msg.tool_name is None

    def test_id_missing_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(
                role="user",
                timestamp="2026-05-05T10:00:00Z",
            )

    def test_timestamp_missing_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(
                id="msg-005",
                role="user",
            )

    @pytest.mark.parametrize("role", ["user", "assistant", "tool"])
    def test_role_valid_accepted(self, role: str) -> None:
        msg = ChatMessage(
            id="msg-006",
            role=role,
            timestamp="2026-05-05T10:00:00Z",
        )
        assert msg.role == role

    def test_role_invalid_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(
                id="msg-007",
                role="invalid_role",
                timestamp="2026-05-05T10:00:00Z",
            )

    def test_tool_role_call_fields_set(self) -> None:
        msg = ChatMessage(
            id="msg-009",
            role="tool",
            content="result payload",
            tool_call_id="call-42",
            tool_name="list_networks",
            timestamp="2026-05-05T10:00:00Z",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call-42"
        assert msg.tool_name == "list_networks"

    def test_extra_fields_ignored(self) -> None:
        msg = ChatMessage(
            id="msg-010",
            role="user",
            timestamp="2026-05-05T10:00:00Z",
            unknown_field="ignored",  # type: ignore[call-arg]
        )
        assert msg.id == "msg-010"
        assert not hasattr(msg, "unknown_field")


class TestChatContext:
    def test_defaults_none_and_empty_list(self) -> None:
        ctx = ChatContext()
        assert ctx.active_network_id is None
        assert ctx.active_network_name is None
        assert ctx.pinned_network_ids == []

    def test_active_network_id_set(self) -> None:
        ctx = ChatContext(active_network_id="net-123")
        assert ctx.active_network_id == "net-123"
        assert ctx.active_network_name is None

    def test_active_network_name_set(self) -> None:
        ctx = ChatContext(active_network_name="My Network")
        assert ctx.active_network_name == "My Network"
        assert ctx.active_network_id is None

    def test_pinned_network_ids_set(self) -> None:
        ctx = ChatContext(pinned_network_ids=["net-1", "net-2"])
        assert ctx.pinned_network_ids == ["net-1", "net-2"]

    def test_all_fields_set(self) -> None:
        ctx = ChatContext(
            active_network_id="net-42",
            active_network_name="Test Network",
            pinned_network_ids=["net-1", "net-2"],
        )
        assert ctx.active_network_id == "net-42"
        assert ctx.active_network_name == "Test Network"
        assert ctx.pinned_network_ids == ["net-1", "net-2"]

    def test_pinned_network_ids_distinct_per_instance(self) -> None:
        ctx1 = ChatContext()
        ctx2 = ChatContext()
        assert ctx1.pinned_network_ids == []
        assert ctx2.pinned_network_ids == []
        assert ctx1.pinned_network_ids is not ctx2.pinned_network_ids

    def test_extra_fields_ignored(self) -> None:
        ctx = ChatContext(unknown_field="ignored")  # type: ignore[call-arg]
        assert not hasattr(ctx, "unknown_field")


class TestChatRequest:
    def test_messages_only_default_context(self) -> None:
        msg = ChatMessage(
            id="msg-001",
            role="user",
            content="Hello",
            timestamp="2026-05-05T10:00:00Z",
        )
        req = ChatRequest(messages=[msg])
        assert req.messages == [msg]
        assert req.context == ChatContext()

    def test_messages_and_context_set(self) -> None:
        msg = ChatMessage(
            id="msg-001",
            role="user",
            content="Hello",
            timestamp="2026-05-05T10:00:00Z",
        )
        ctx = ChatContext(
            active_network_id="net-42",
            active_network_name="My Network",
        )
        req = ChatRequest(messages=[msg], context=ctx)
        assert req.messages == [msg]
        assert req.context == ctx

    def test_empty_messages_list_accepted(self) -> None:
        req = ChatRequest(messages=[])
        assert req.messages == []

    def test_multiple_messages_order_preserved(self) -> None:
        msg1 = ChatMessage(
            id="msg-001",
            role="user",
            content="Q1",
            timestamp="2026-05-05T10:00:00Z",
        )
        msg2 = ChatMessage(
            id="msg-002",
            role="assistant",
            content="A1",
            timestamp="2026-05-05T10:00:01Z",
        )
        req = ChatRequest(messages=[msg1, msg2])
        assert len(req.messages) == 2
        assert req.messages[0] == msg1
        assert req.messages[1] == msg2

    def test_messages_missing_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest()

    def test_extra_fields_ignored(self) -> None:
        req = ChatRequest(messages=[], unknown_field="ignored")  # type: ignore[call-arg]
        assert not hasattr(req, "unknown_field")


class TestChatRequestModelDumpRoundTrip:
    def test_model_dump_round_trip_minimal(self) -> None:
        msg = ChatMessage(
            id="msg-001",
            role="user",
            content="Hello",
            timestamp="2026-05-05T10:00:00Z",
        )
        req = ChatRequest(messages=[msg])
        data = req.model_dump()
        recreated = ChatRequest(**data)
        assert recreated == req

    def test_model_dump_round_trip_full_context(self) -> None:
        msg = ChatMessage(
            id="msg-001",
            role="user",
            content="What networks do I have?",
            timestamp="2026-05-05T10:00:00Z",
        )
        ctx = ChatContext(
            active_network_id="net-42",
            active_network_name="My Network",
            pinned_network_ids=["net-1"],
        )
        req = ChatRequest(messages=[msg], context=ctx)
        data = req.model_dump()
        recreated = ChatRequest(**data)
        assert recreated == req
        assert recreated.context.active_network_id == "net-42"
        assert recreated.context.pinned_network_ids == ["net-1"]
