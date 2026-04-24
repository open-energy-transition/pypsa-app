"""LLM tool registry.

Tools are auto-discovered from this package: each module in this directory
that exposes ``NAME``, ``DESCRIPTION``, ``INPUT_SCHEMA``, and ``handler`` is
registered automatically. To add a new tool, create a new module — no other
file needs to change.
"""

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_REQUIRED_ATTRS = ("NAME", "DESCRIPTION", "INPUT_SCHEMA", "handler")


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


def _discover() -> dict[str, "Tool"]:
    tools: dict[str, Tool] = {}
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        if not all(hasattr(module, a) for a in _REQUIRED_ATTRS):
            logger.warning(
                "Skipping LLM tool module %s: missing one of %s",
                module_info.name,
                _REQUIRED_ATTRS,
            )
            continue
        tool = Tool(
            name=module.NAME,
            description=module.DESCRIPTION,
            input_schema=module.INPUT_SCHEMA,
            handler=module.handler,
        )
        tools[tool.name] = tool
    return tools


REGISTRY: dict[str, Tool] = _discover()


def anthropic_tool_specs() -> list[dict[str, Any]]:
    """Format the registry for the Anthropic API ``tools`` parameter."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in REGISTRY.values()
    ]


__all__ = ["REGISTRY", "Tool", "anthropic_tool_specs"]
