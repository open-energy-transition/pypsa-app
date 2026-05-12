"""Tests for LLMSettings — provider fields and generation params."""

import os
from unittest.mock import patch

from pydantic_settings import BaseSettings

from pypsa_app.backend.settings import Settings
from pypsa_app.llm.settings import LLMSettings


def test_llm_settings_defaults_when_env_unset() -> None:
    """All fields must have sensible defaults when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        assert settings.llm_provider == "openai"
        assert settings.llm_model == "qwen3.5:9b"
        assert settings.llm_api_key == ""
        assert settings.llm_api_base is None
        assert settings.llm_internal_api_base is None
        assert settings.llm_internal_port == 8000
        assert settings.llm_max_tokens == 2048
        assert settings.llm_temperature == 0.2
        assert settings.llm_request_timeout_seconds == 120.0
        assert settings.chat_enabled is False
        assert settings.llm_max_tool_iterations == 8


def test_llm_settings_parses_all_fields_from_env() -> None:
    """All fields must be read from their env-var aliases."""
    env = {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-sonnet-4-6",
        "LLM_API_KEY": "sk-ant-...",
        "LLM_API_BASE": "https://api.anthropic.com",
        "LLM_MAX_TOKENS": "4096",
        "LLM_TEMPERATURE": "0.7",
        "LLM_REQUEST_TIMEOUT_SECONDS": "60.0",
        "CHAT_ENABLED": "true",
        "LLM_MAX_TOOL_ITERATIONS": "16",
        "LLM_INTERNAL_API_BASE": "http://127.0.0.1:8000",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.llm_provider == "anthropic"
        assert settings.llm_model == "claude-sonnet-4-6"
        assert settings.llm_api_key == "sk-ant-..."
        assert settings.llm_api_base == "https://api.anthropic.com"
        assert settings.llm_max_tokens == 4096
        assert settings.llm_temperature == 0.7
        assert settings.llm_request_timeout_seconds == 60.0
        assert settings.chat_enabled is True
        assert settings.llm_max_tool_iterations == 16
        assert settings.llm_internal_api_base == "http://127.0.0.1:8000"


def test_llm_settings_parses_provider_individually_from_env() -> None:
    """LLM_PROVIDER env var must override the default provider."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}, clear=True):
        settings = LLMSettings()
        assert settings.llm_provider == "anthropic"


def test_llm_settings_parses_model_individually_from_env() -> None:
    """LLM_MODEL env var must override the default model."""
    with patch.dict(os.environ, {"LLM_MODEL": "claude-sonnet-4-6"}, clear=True):
        settings = LLMSettings()
        assert settings.llm_model == "claude-sonnet-4-6"


def test_llm_settings_parses_api_key_individually_from_env() -> None:
    """LLM_API_KEY env var must be parsed as a string."""
    with patch.dict(os.environ, {"LLM_API_KEY": "sk-ant-..."}, clear=True):
        settings = LLMSettings()
        assert settings.llm_api_key == "sk-ant-..."


def test_llm_settings_parses_api_base_individually_from_env() -> None:
    """LLM_API_BASE env var must override the default (None)."""
    with patch.dict(
        os.environ,
        {"LLM_API_BASE": "https://api.anthropic.com"},
        clear=True,
    ):
        settings = LLMSettings()
        assert settings.llm_api_base == "https://api.anthropic.com"


def test_llm_settings_extra_env_vars_are_ignored() -> None:
    """Extra, unrecognized env vars must not cause validation errors."""
    with patch.dict(
        os.environ,
        {"UNRELATED_VAR": "should-be-ignored"},
        clear=True,
    ):
        settings = LLMSettings()
        assert settings.llm_provider == "openai"  # still default


def test_llm_settings_parses_max_tokens_from_env() -> None:
    """LLM_MAX_TOKENS env var must be parsed as an int."""
    with patch.dict(os.environ, {"LLM_MAX_TOKENS": "4096"}, clear=True):
        settings = LLMSettings()
        assert settings.llm_max_tokens == 4096


def test_llm_settings_parses_temperature_from_env() -> None:
    """LLM_TEMPERATURE env var must be parsed as a float."""
    with patch.dict(os.environ, {"LLM_TEMPERATURE": "0.7"}, clear=True):
        settings = LLMSettings()
        assert settings.llm_temperature == 0.7


def test_llm_settings_parses_request_timeout_from_env() -> None:
    """LLM_REQUEST_TIMEOUT_SECONDS env var must be parsed as a float."""
    with patch.dict(os.environ, {"LLM_REQUEST_TIMEOUT_SECONDS": "60.0"}, clear=True):
        settings = LLMSettings()
        assert settings.llm_request_timeout_seconds == 60.0


def test_llm_settings_parses_chat_enabled_true_as_truthy() -> None:
    """CHAT_ENABLED='true' must be parsed as True."""
    with patch.dict(os.environ, {"CHAT_ENABLED": "true"}, clear=True):
        settings = LLMSettings()
        assert settings.chat_enabled is True


def test_llm_settings_parses_chat_enabled_one_as_truthy() -> None:
    """CHAT_ENABLED='1' must be parsed as True."""
    with patch.dict(os.environ, {"CHAT_ENABLED": "1"}, clear=True):
        settings = LLMSettings()
        assert settings.chat_enabled is True


def test_llm_settings_parses_chat_enabled_yes_as_truthy() -> None:
    """CHAT_ENABLED='yes' must be parsed as True."""
    with patch.dict(os.environ, {"CHAT_ENABLED": "yes"}, clear=True):
        settings = LLMSettings()
        assert settings.chat_enabled is True


def test_llm_settings_defaults_chat_enabled_to_false_when_env_unset() -> None:
    """CHAT_ENABLED must default to false when env var is unset."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        assert settings.chat_enabled is False


def test_llm_settings_parses_max_tool_iterations_from_env() -> None:
    """LLM_MAX_TOOL_ITERATIONS env var must be parsed as an int."""
    with patch.dict(os.environ, {"LLM_MAX_TOOL_ITERATIONS": "16"}, clear=True):
        settings = LLMSettings()
        assert settings.llm_max_tool_iterations == 16


def test_llm_settings_is_pydantic_settings_instance() -> None:
    """LLMSettings must derive from pydantic-settings BaseSettings."""
    assert issubclass(LLMSettings, BaseSettings)


def test_model_string_defaults_to_openai_qwen3_5() -> None:
    """model_string must return openai/qwen3.5:9b with default provider and model."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        assert settings.model_string == "openai/qwen3.5:9b"


def test_model_string_composes_anthropic_claude() -> None:
    """model_string must return anthropic/claude-sonnet-4-6 when both fields are set."""
    env = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-sonnet-4-6"}
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.model_string == "anthropic/claude-sonnet-4-6"


def test_model_string_handles_nested_slash_in_model() -> None:
    """model_string must preserve slashes in the model portion."""
    env = {"LLM_PROVIDER": "openrouter", "LLM_MODEL": "anthropic/claude-sonnet-4"}
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.model_string == "openrouter/anthropic/claude-sonnet-4"


def test_model_string_updates_when_provider_changes() -> None:
    """model_string must reflect runtime changes to llm_provider."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        settings.llm_provider = "anthropic"
        assert settings.model_string == "anthropic/qwen3.5:9b"


def test_model_string_updates_when_model_changes() -> None:
    """model_string must reflect runtime changes to llm_model."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        settings.llm_model = "claude-sonnet-4-6"
        assert settings.model_string == "openai/claude-sonnet-4-6"


def test_llm_settings_parses_llm_internal_api_base_from_env() -> None:
    """LLM_INTERNAL_API_BASE env var must be parsed."""
    with patch.dict(
        os.environ,
        {"LLM_INTERNAL_API_BASE": "http://127.0.0.1:8000"},
        clear=True,
    ):
        settings = LLMSettings()
        assert settings.llm_internal_api_base == "http://127.0.0.1:8000"


def test_backend_settings_composes_llm_settings() -> None:
    """backend Settings must expose LLMSettings via the 'llm' attribute."""
    with patch.dict(os.environ, {}, clear=True):
        backend_settings = Settings()
        assert isinstance(backend_settings.llm, LLMSettings)


def test_backend_settings_llm_attribute_defaults() -> None:
    """backend Settings.llm defaults must match LLMSettings defaults."""
    with patch.dict(os.environ, {}, clear=True):
        backend_settings = Settings()
        assert backend_settings.llm.chat_enabled is False
        assert backend_settings.llm.llm_max_tool_iterations == 8
        assert backend_settings.llm.llm_provider == "openai"


def test_backend_settings_llm_model_string_default() -> None:
    """backend Settings().llm.model_string must return the default openai/qwen3.5:9b."""
    with patch.dict(os.environ, {}, clear=True):
        backend_settings = Settings()
        assert backend_settings.llm.model_string == "openai/qwen3.5:9b"


def test_backend_settings_llm_reads_from_env() -> None:
    """backend Settings.llm must read LLM fields from environment."""
    env = {
        "CHAT_ENABLED": "true",
        "LLM_MAX_TOOL_ITERATIONS": "16",
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-sonnet-4-6",
        "LLM_INTERNAL_API_BASE": "http://127.0.0.1:8000",
    }
    with patch.dict(os.environ, env, clear=True):
        backend_settings = Settings()
        assert backend_settings.llm.chat_enabled is True
        assert backend_settings.llm.llm_max_tool_iterations == 16
        assert backend_settings.llm.llm_provider == "anthropic"
        assert backend_settings.llm.llm_model == "claude-sonnet-4-6"
        assert backend_settings.llm.llm_internal_api_base == "http://127.0.0.1:8000"


def test_resolved_internal_api_base_returns_explicit_value_when_set() -> None:
    """resolved_internal_api_base returns explicit llm_internal_api_base when set."""
    env = {"LLM_INTERNAL_API_BASE": "http://custom:9000/api"}
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.resolved_internal_api_base == "http://custom:9000/api"


def test_resolved_internal_api_base_defaults_from_port_when_unset() -> None:
    """resolved_internal_api_base defaults to http://127.0.0.1:8000 when env unset."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        assert settings.resolved_internal_api_base == "http://127.0.0.1:8000"


def test_resolved_internal_api_base_uses_custom_port_when_unset() -> None:
    """resolved_internal_api_base uses llm_internal_port when api_base is unset."""
    env = {"LLM_INTERNAL_PORT": "9000"}
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.resolved_internal_api_base == "http://127.0.0.1:9000"


def test_resolved_internal_api_base_explicit_takes_precedence_over_port() -> None:
    """resolved_internal_api_base prefers explicit value over port default."""
    env = {
        "LLM_INTERNAL_API_BASE": "http://explicit:3000",
        "LLM_INTERNAL_PORT": "9000",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.resolved_internal_api_base == "http://explicit:3000"


def test_llm_internal_port_defaults_to_8000() -> None:
    """llm_internal_port must default to 8000 when env is unset."""
    with patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings()
        assert settings.llm_internal_port == 8000


def test_llm_internal_port_parsed_from_env() -> None:
    """llm_internal_port must be read from LLM_INTERNAL_PORT env var."""
    env = {"LLM_INTERNAL_PORT": "9000"}
    with patch.dict(os.environ, env, clear=True):
        settings = LLMSettings()
        assert settings.llm_internal_port == 9000
