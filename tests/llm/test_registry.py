"""Tests for the LLM tool registry auto-discovery."""

from __future__ import annotations

import importlib
from pathlib import Path

from pypsa_app.llm import tools as tools_pkg


def test_list_networks_is_registered():
    assert "list_networks" in tools_pkg.REGISTRY
    tool = tools_pkg.REGISTRY["list_networks"]
    assert tool.name == "list_networks"
    assert callable(tool.handler)


def test_get_network_detail_is_registered():
    assert "get_network_detail" in tools_pkg.REGISTRY
    tool = tools_pkg.REGISTRY["get_network_detail"]
    assert tool.name == "get_network_detail"
    assert callable(tool.handler)


def test_anthropic_tool_specs_shape():
    specs = tools_pkg.anthropic_tool_specs()
    names = {s["name"] for s in specs}
    assert "list_networks" in names
    assert "get_network_detail" in names
    for spec in specs:
        assert set(spec.keys()) == {"name", "description", "input_schema"}


def test_underscore_prefixed_modules_are_skipped(tmp_path, monkeypatch):
    """Private modules (leading underscore) must not be registered."""
    pkg_dir = Path(tools_pkg.__path__[0])
    hidden = pkg_dir / "_hidden_tool.py"
    hidden.write_text(
        'NAME = "hidden"\nDESCRIPTION = "should be skipped"\n'
        'INPUT_SCHEMA = {"type": "object"}\n'
        "def handler(**kw):\n    return {}\n"
    )
    try:
        importlib.invalidate_caches()
        discovered = tools_pkg._discover()
        assert "hidden" not in discovered
    finally:
        hidden.unlink(missing_ok=True)


def test_modules_missing_required_attrs_are_skipped(tmp_path):
    """A module without NAME/DESCRIPTION/INPUT_SCHEMA/handler is skipped."""
    pkg_dir = Path(tools_pkg.__path__[0])
    broken = pkg_dir / "broken_tool.py"
    broken.write_text('NAME = "broken"\n# missing DESCRIPTION/INPUT_SCHEMA/handler\n')
    try:
        importlib.invalidate_caches()
        discovered = tools_pkg._discover()
        assert "broken" not in discovered
    finally:
        broken.unlink(missing_ok=True)


def test_valid_drop_in_module_is_discovered():
    """Any file with the 4 required attrs is picked up without edits."""
    pkg_dir = Path(tools_pkg.__path__[0])
    drop_in = pkg_dir / "drop_in_tool.py"
    drop_in.write_text(
        'NAME = "drop_in"\nDESCRIPTION = "demo"\n'
        'INPUT_SCHEMA = {"type": "object"}\n'
        "def handler(**kw):\n    return {}\n"
    )
    try:
        importlib.invalidate_caches()
        discovered = tools_pkg._discover()
        assert "drop_in" in discovered
    finally:
        drop_in.unlink(missing_ok=True)
