"""Live provider smoke tests — require a real LLM provider.

All tests in this module are marked with ``@pytest.mark.live`` and are
**skipped by default**.  Run them explicitly with:

    pytest -m live tests/llm/test_live_provider.py

Requires ``LLM_API_KEY`` and ``LLM_API_BASE`` to be set in the
environment.
"""

from __future__ import annotations

import os

import pytest

from pypsa_app.llm.client import LLMClient
from pypsa_app.llm.settings import LLMSettings

pytestmark = pytest.mark.live


@pytest.mark.anyio
async def test_live_provider_streaming_round_trip() -> None:
    """Validate a single streaming round-trip against the configured LLM provider.

    Sends one user message and asserts the provider returns at least one
    chunk of response content. Skipped when no provider credentials are
    configured.
    """
    if not os.environ.get("LLM_API_KEY") and not os.environ.get("LLM_API_BASE"):
        pytest.skip("LLM_API_KEY or LLM_API_BASE not set")

    settings = LLMSettings()
    client = LLMClient(settings)

    messages: list[dict[str, str]] = [
        {"role": "user", "content": "Say hello in one word."}
    ]
    chunks = [chunk async for chunk in client.stream(messages)]

    assert len(chunks) > 0


@pytest.mark.anyio
async def test_live_provider_health_ping() -> None:
    """Validate the health() ping reaches the configured LLM provider.

    health() pings the provider with a 1-token completion and returns
    ``{"ok": True, "model": …}`` on success. Skipped when no provider
    credentials are configured.
    """
    if not os.environ.get("LLM_API_KEY") and not os.environ.get("LLM_API_BASE"):
        pytest.skip("LLM_API_KEY or LLM_API_BASE not set")

    settings = LLMSettings()
    client = LLMClient(settings)

    result = await client.health()

    assert result["ok"] is True
    assert "model" in result
