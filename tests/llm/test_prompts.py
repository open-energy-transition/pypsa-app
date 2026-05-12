"""Tests for system-prompt constants and build_system_prompt builder."""

from __future__ import annotations

from pypsa_app.llm.api.schemas import ChatContext
from pypsa_app.llm.prompts import BASE_SYSTEM_PROMPT, build_system_prompt


class TestBaseSystemPrompt:
    """Contract tests for the BASE_SYSTEM_PROMPT constant."""

    def test_is_non_empty_string(self) -> None:
        assert isinstance(BASE_SYSTEM_PROMPT, str)
        assert len(BASE_SYSTEM_PROMPT) > 0

    def test_contains_core_copilot_message(self) -> None:
        assert "copilot" in BASE_SYSTEM_PROMPT.lower()
        assert "PyPSA App" in BASE_SYSTEM_PROMPT

    def test_contains_tool_usage_guidance(self) -> None:
        assert "tools" in BASE_SYSTEM_PROMPT.lower()
        assert "invent" in BASE_SYSTEM_PROMPT.lower()

    def test_contains_result_summarisation_guidance(self) -> None:
        assert "summarise" in BASE_SYSTEM_PROMPT.lower()
        assert "plain language" in BASE_SYSTEM_PROMPT.lower()


class TestBuildSystemPrompt:
    """Contract tests for build_system_prompt across all context combinations."""

    def test_empty_context_returns_only_base_prompt(self) -> None:
        """With no active network and no pinned IDs, only BASE_SYSTEM_PROMPT."""
        ctx = ChatContext()
        result = build_system_prompt(ctx)
        assert result == BASE_SYSTEM_PROMPT

    def test_active_network_only_includes_active_paragraph(self) -> None:
        """With active_network set but no pinned IDs, includes active paragraph."""
        ctx = ChatContext(
            active_network_id="net_123",
            active_network_name="German Grid",
        )
        result = build_system_prompt(ctx)

        assert result.startswith(BASE_SYSTEM_PROMPT)
        assert "German Grid" in result
        assert "net_123" in result
        assert "deictic" in result
        assert "list_networks" in result
        # Should NOT contain pinned section
        assert "pinned to this conversation" not in result

    def test_pinned_only_includes_pinned_paragraph(self) -> None:
        """With pinned IDs but no active network, includes pinned paragraph."""
        ctx = ChatContext(
            pinned_network_ids=["net_a", "net_b"],
        )
        result = build_system_prompt(ctx)

        assert result.startswith(BASE_SYSTEM_PROMPT)
        assert "pinned to this conversation" in result
        assert "net_a" in result
        assert "net_b" in result
        # Should NOT contain active network deictic references
        assert "deictic" not in result

    def test_both_active_and_pinned_includes_both_paragraphs(self) -> None:
        """With both active network and pinned IDs, both paragraphs present."""
        ctx = ChatContext(
            active_network_id="n1",
            active_network_name="Grid A",
            pinned_network_ids=["n2", "n3"],
        )
        result = build_system_prompt(ctx)

        assert result.startswith(BASE_SYSTEM_PROMPT)
        assert "Grid A" in result
        assert "deictic" in result
        assert "pinned to this conversation" in result
        assert "n2" in result
        assert "n3" in result
        # Sections are separated by double newline
        assert "\n\n" in result

    def test_active_network_name_none_no_active_paragraph(self) -> None:
        """When active_network_name is None, no active paragraph even if id set."""
        ctx = ChatContext(
            active_network_id="net_123",
            active_network_name=None,
        )
        result = build_system_prompt(ctx)
        assert result == BASE_SYSTEM_PROMPT

    def test_active_network_id_none_no_active_paragraph(self) -> None:
        """When active_network_id is None, no active paragraph even if name set."""
        ctx = ChatContext(
            active_network_id=None,
            active_network_name="Grid A",
        )
        result = build_system_prompt(ctx)
        assert result == BASE_SYSTEM_PROMPT

    def test_empty_pinned_ids_list_no_pinned_paragraph(self) -> None:
        """An empty pinned_network_ids list produces no pinned paragraph."""
        ctx = ChatContext(
            active_network_id="n1",
            active_network_name="Grid A",
            pinned_network_ids=[],
        )
        result = build_system_prompt(ctx)
        assert "pinned to this conversation" not in result
