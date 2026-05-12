"""Test that every module in the llm package scaffold is importable."""

from __future__ import annotations

import pytest

from pypsa_app.llm.exceptions import (
    ChatDisabledError,
    LLMProviderError,
    ToolExecutionError,
)


def test_import_llm_package_succeeds() -> None:
    """The top-level llm package must be importable."""
    import pypsa_app.llm  # noqa: F401


def test_import_settings_succeeds() -> None:
    """settings.py must be importable."""
    from pypsa_app.llm import settings  # noqa: F401


def test_import_exceptions_exports_classes() -> None:
    """exceptions.py must export the three custom exception classes."""
    assert issubclass(ChatDisabledError, Exception)
    assert issubclass(LLMProviderError, Exception)
    assert issubclass(ToolExecutionError, Exception)


def test_import_client_succeeds() -> None:
    """client.py must be importable."""
    from pypsa_app.llm import client  # noqa: F401


def test_import_events_succeeds() -> None:
    """events.py must be importable."""
    from pypsa_app.llm import events  # noqa: F401


def test_import_prompts_succeeds() -> None:
    """prompts.py must be importable."""
    from pypsa_app.llm import prompts  # noqa: F401


def test_import_service_succeeds() -> None:
    """service.py must be importable."""
    from pypsa_app.llm import service  # noqa: F401


def test_import_tools_package_succeeds() -> None:
    """tools/__init__.py must be importable."""
    from pypsa_app.llm import tools  # noqa: F401


def test_import_tools_base_succeeds() -> None:
    """tools/base.py must be importable."""
    from pypsa_app.llm.tools import base  # noqa: F401


def test_import_tools_http_client_succeeds() -> None:
    """tools/http_client.py must be importable."""
    from pypsa_app.llm.tools import http_client  # noqa: F401


def test_import_tools_list_networks_succeeds() -> None:
    """tools/list_networks.py must be importable."""
    from pypsa_app.llm.tools import list_networks  # noqa: F401


def test_import_tools_get_network_detail_succeeds() -> None:
    """tools/get_network_detail.py must be importable."""
    from pypsa_app.llm.tools import get_network_detail  # noqa: F401


def test_import_tools_get_network_statistics_succeeds() -> None:
    """tools/get_network_statistics.py must be importable."""
    from pypsa_app.llm.tools import get_network_statistics  # noqa: F401


def test_import_api_package_succeeds() -> None:
    """api/__init__.py must be importable."""
    from pypsa_app.llm import api  # noqa: F401


def test_import_api_deps_succeeds() -> None:
    """api/deps.py must be importable."""
    from pypsa_app.llm.api import deps  # noqa: F401


def test_import_api_routes_succeeds() -> None:
    """api/routes.py must be importable."""
    from pypsa_app.llm.api import routes  # noqa: F401


def test_import_api_schemas_succeeds() -> None:
    """api/schemas.py must be importable."""
    from pypsa_app.llm.api import schemas  # noqa: F401


@pytest.mark.parametrize(
    ("exc_cls", "message"),
    [
        (ChatDisabledError, "chat is disabled"),
        (LLMProviderError, "provider error"),
        (ToolExecutionError, "tool error"),
    ],
)
def test_exception_is_raisable_and_catchable(
    exc_cls: type[Exception],
    message: str,
) -> None:
    """Each custom exception must be raisable with a message and catchable."""
    with pytest.raises(exc_cls, match=message):
        raise exc_cls(message)
