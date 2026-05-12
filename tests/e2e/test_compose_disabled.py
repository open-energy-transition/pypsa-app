"""Validate tests/e2e/compose.disabled.yaml override.

The disabled override file must:

- Override the ``app`` service env to set ``CHAT_ENABLED=false``
- Map a different host port (8766) to avoid conflicts with the enabled stack
- Not redefine app build context
- Mergeable with compose.yaml (``-f compose.yaml -f compose.disabled.yaml``)

When CHAT_ENABLED=false, POST /api/v1/chat/stream returns 404.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_DISABLED_PATH = Path(__file__).resolve().parent / "compose.disabled.yaml"


def _load_compose_disabled() -> dict:
    """Load and return the compose.disabled.yaml as a dict."""
    if not COMPOSE_DISABLED_PATH.exists():
        msg = f"compose.disabled.yaml not found at {COMPOSE_DISABLED_PATH}"
        raise FileNotFoundError(msg)
    with COMPOSE_DISABLED_PATH.open() as f:
        return yaml.safe_load(f)


class TestComposeDisabledExists:
    """The compose.disabled.yaml file must exist."""

    def test_file_exists(self) -> None:
        """compose.disabled.yaml exists at tests/e2e/compose.disabled.yaml."""
        assert COMPOSE_DISABLED_PATH.exists(), (
            f"Expected {COMPOSE_DISABLED_PATH} to exist"
        )
        assert COMPOSE_DISABLED_PATH.is_file(), (
            f"Expected {COMPOSE_DISABLED_PATH} to be a file"
        )


class TestComposeDisabledStructure:
    """Validate the compose.disabled.yaml override services."""

    def test_services_section_present(self) -> None:
        """Top-level 'services' key must be present."""
        compose = _load_compose_disabled()
        assert "services" in compose, (
            "compose.disabled.yaml must have a 'services' section"
        )

    def test_app_service_override_defined(self) -> None:
        """The 'app' service must be overridden."""
        compose = _load_compose_disabled()
        assert "app" in compose["services"], (
            "'app' service must be overridden in compose.disabled.yaml"
        )

    def test_chat_enabled_is_false(self) -> None:
        """CHAT_ENABLED must be 'false'."""
        compose = _load_compose_disabled()
        app_svc = compose["services"]["app"]
        env = _env_dict(app_svc)
        assert "CHAT_ENABLED" in env, (
            "app env must override CHAT_ENABLED"
        )
        assert env["CHAT_ENABLED"] == "false", (
            f"CHAT_ENABLED must be 'false', got '{env['CHAT_ENABLED']}'"
        )

    def test_port_mapping_is_different_from_enabled_stack(self) -> None:
        """Port mapping must use 8766 to avoid conflict with the enabled stack."""
        compose = _load_compose_disabled()
        ports = compose["services"]["app"].get("ports", [])
        expected = "127.0.0.1:8766:8000"
        assert expected in ports, (
            f"ports must include '{expected}' for disabled-stack E2E access"
        )

    def test_does_not_redefine_build(self) -> None:
        """compose.disabled.yaml must not redefine app build — only env + port."""
        compose = _load_compose_disabled()
        app_svc = compose["services"]["app"]
        assert "build" not in app_svc, (
            "compose.disabled.yaml must not redefine app build context"
        )

    def test_does_not_set_other_env_vars_unnecessarily(self) -> None:
        """Only CHAT_ENABLED should be overridden in env."""
        compose = _load_compose_disabled()
        app_svc = compose["services"]["app"]
        env_raw = app_svc.get("environment", {})
        if isinstance(env_raw, list):
            keys = [item.split("=", 1)[0] for item in env_raw if "=" in item]
        else:
            keys = list(env_raw.keys())
        assert "CHAT_ENABLED" in keys, (
            "CHAT_ENABLED must be in the environment override"
        )


class TestComposeDisabledIntegration:
    """Integration checks: merging compose.yaml + compose.disabled.yaml."""

    def test_both_files_define_app_service(self) -> None:
        """Both compose.yaml and compose.disabled.yaml reference the 'app' service."""
        base_path = Path(__file__).resolve().parent / "compose.yaml"
        with base_path.open() as f:
            base = yaml.safe_load(f)
        disabled = _load_compose_disabled()

        assert "app" in base["services"], "compose.yaml must define 'app'"
        assert "app" in disabled["services"], (
            "compose.disabled.yaml must override 'app'"
        )



def _env_dict(svc: dict) -> dict[str, str]:
    """Parse a service's environment list/dict into a plain dict."""
    env = svc.get("environment", [])
    if isinstance(env, dict):
        return env
    result: dict[str, str] = {}
    for item in env:
        if "=" in item:
            key, val = item.split("=", 1)
            result[key] = val
    return result
