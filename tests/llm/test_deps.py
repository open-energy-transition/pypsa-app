"""Tests for FastAPI dependency providers in llm.api.deps."""

from __future__ import annotations

import os
from unittest.mock import patch

import httpx

from pypsa_app.backend.settings import Settings
from pypsa_app.llm.client import LLMClient
from pypsa_app.llm.service import ChatService
from pypsa_app.llm.tools import ToolRegistry


def test_get_llm_client_returns_llm_client_instance() -> None:
    """get_llm_client must return an LLMClient built from settings.llm."""
    from pypsa_app.llm.api.deps import get_llm_client

    env = {"CHAT_ENABLED": "false"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        client = get_llm_client(settings)

    assert isinstance(client, LLMClient)


def test_get_internal_http_client_returns_async_client() -> None:
    """get_internal_http_client must return an httpx.AsyncClient."""
    from pypsa_app.llm.api.deps import get_internal_http_client

    env = {"CHAT_ENABLED": "false"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        http = get_internal_http_client(settings)

    assert isinstance(http, httpx.AsyncClient)


def test_get_tool_registry_returns_tool_registry_with_default_tools() -> None:
    """get_tool_registry must return a ToolRegistry containing all default tools."""
    from pypsa_app.llm.api.deps import (
        get_internal_http_client,
        get_tool_registry,
    )

    env = {"CHAT_ENABLED": "false"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        http = get_internal_http_client(settings)
        registry = get_tool_registry(http)

    assert isinstance(registry, ToolRegistry)

    schemas = registry.schemas()
    assert len(schemas) == 3

    names = {s["function"]["name"] for s in schemas}
    assert names == {
        "list_networks",
        "get_network_detail",
        "get_network_statistics",
    }


def test_get_chat_service_returns_chat_service_instance() -> None:
    """get_chat_service returns a ChatService wired with client, tools, and settings."""
    from pypsa_app.llm.api.deps import (
        get_chat_service,
        get_internal_http_client,
        get_llm_client,
        get_tool_registry,
    )

    env = {"CHAT_ENABLED": "false"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        client = get_llm_client(settings)
        http = get_internal_http_client(settings)
        registry = get_tool_registry(http)
        service = get_chat_service(client, registry, settings)

    assert isinstance(service, ChatService)
