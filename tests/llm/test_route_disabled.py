"""Tests for require_chat_enabled dependency — feature-gating the chat endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from pypsa_app.backend.settings import Settings
from pypsa_app.llm.api.deps import require_chat_enabled


def test_require_chat_enabled_does_not_raise_when_chat_enabled_is_true() -> None:
    """require_chat_enabled must not raise when settings.llm.chat_enabled is True."""
    env = {"CHAT_ENABLED": "true"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        # Must not raise
        require_chat_enabled(settings)


def test_require_chat_enabled_raises_404_when_chat_enabled_is_false() -> None:
    """require_chat_enabled must raise 404 HTTPException when chat is disabled."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        with pytest.raises(HTTPException) as exc_info:
            require_chat_enabled(settings)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "chat is disabled"
