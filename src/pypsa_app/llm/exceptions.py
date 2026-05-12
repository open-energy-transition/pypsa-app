"""Custom exceptions for the LLM chat module."""

from __future__ import annotations


class ChatDisabledError(Exception):
    """Raised when chat is requested but CHAT_ENABLED is false."""


class LLMProviderError(Exception):
    """Raised when the LLM provider call fails."""


class ToolExecutionError(Exception):
    """Raised when an LLM tool call returns an error."""
