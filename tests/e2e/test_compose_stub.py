"""Validate tests/e2e/compose.stub.yaml override structure.

The stub override file must:

- Define a ``stub-llm`` service building from ``./stub-llm``
- Map port 8766 → 8000 (host → container)
- Override the ``app`` service env vars for LLM_API_BASE and LLM_API_KEY
  to point at the stub-LLM container

When LLM_API_KEY is unset, the harness brings up stub-llm.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_STUB_PATH = Path(__file__).resolve().parent / "compose.stub.yaml"


def _load_compose_stub() -> dict:
    """Load and return the compose.stub.yaml as a dict."""
    if not COMPOSE_STUB_PATH.exists():
        msg = f"compose.stub.yaml not found at {COMPOSE_STUB_PATH}"
        raise FileNotFoundError(msg)
    with COMPOSE_STUB_PATH.open() as f:
        return yaml.safe_load(f)


class TestComposeStubExists:
    """The compose.stub.yaml file must exist."""

    def test_file_exists(self) -> None:
        """compose.stub.yaml exists at tests/e2e/compose.stub.yaml."""
        assert COMPOSE_STUB_PATH.exists(), f"Expected {COMPOSE_STUB_PATH} to exist"
        assert COMPOSE_STUB_PATH.is_file(), f"Expected {COMPOSE_STUB_PATH} to be a file"


class TestComposeStubStructure:
    """Validate the compose.stub.yaml override services."""

    def test_services_section_present(self) -> None:
        """Top-level 'services' key must be present."""
        compose = _load_compose_stub()
        assert "services" in compose, "compose.stub.yaml must have a 'services' section"

    def test_stub_llm_service_defined(self) -> None:
        """A 'stub-llm' service must be defined."""
        compose = _load_compose_stub()
        assert "stub-llm" in compose["services"], (
            "'stub-llm' service must be defined in override"
        )

    def test_stub_llm_build_context_is_stub_llm_dir(self) -> None:
        """stub-llm build context must be ./stub-llm."""
        compose = _load_compose_stub()
        build = compose["services"]["stub-llm"].get("build", {})
        ctx = build.get("context", "")
        df = build.get("dockerfile", "")
        if not ctx and isinstance(build, str):
            ctx = build
        context_is_stub = ctx in ("./stub_llm", "./stub-llm")
        msg = (
            f"stub-llm build must use ./stub-llm context,"
            f" got context={ctx} dockerfile={df}"
        )
        assert context_is_stub or "stub_llm" in str(df) or "stub-llm" in str(df), msg

    def test_stub_llm_port_mapping(self) -> None:
        """stub-llm port 8000 mapped to 127.0.0.1:8766 for local-only access."""
        compose = _load_compose_stub()
        ports = compose["services"]["stub-llm"].get("ports", [])
        expected = "127.0.0.1:8766:8000"
        assert expected in ports, (
            f"ports must include '{expected}' for stub-LLM E2E access"
        )

    def test_app_service_has_env_override(self) -> None:
        """App service must override LLM_API_BASE and LLM_API_KEY env."""
        compose = _load_compose_stub()
        assert "app" in compose["services"], (
            "compose.stub.yaml must override the 'app' service"
        )

    def test_app_llm_api_base_points_to_stub(self) -> None:
        """LLM_API_BASE must point at stub-llm container."""
        compose = _load_compose_stub()
        app_svc = compose["services"]["app"]
        env = _env_dict(app_svc)
        assert "LLM_API_BASE" in env, "app env must override LLM_API_BASE"
        expected = "http://stub-llm:8000/v1"
        assert env["LLM_API_BASE"] == expected, (
            f"LLM_API_BASE must be '{expected}', got '{env['LLM_API_BASE']}'"
        )

    def test_app_llm_api_key_is_stub(self) -> None:
        """LLM_API_KEY must be set to 'stub' for the stub LLM."""
        compose = _load_compose_stub()
        app_svc = compose["services"]["app"]
        env = _env_dict(app_svc)
        assert "LLM_API_KEY" in env, "app env must override LLM_API_KEY"
        assert env["LLM_API_KEY"] == "stub", (
            f"LLM_API_KEY must be 'stub', got '{env['LLM_API_KEY']}'"
        )

    def test_stub_llm_stub_port_env_set(self) -> None:
        """stub-llm service must set STUB_LLM_PORT=8000 to match port mapping."""
        compose = _load_compose_stub()
        svc = compose["services"]["stub-llm"]
        env = _env_dict(svc)
        assert "STUB_LLM_PORT" in env, (
            "stub-llm must set STUB_LLM_PORT to match container port (8000)"
        )
        assert env["STUB_LLM_PORT"] == "8000", (
            f"STUB_LLM_PORT must be 8000, got '{env.get('STUB_LLM_PORT')}'"
        )


class TestComposeStubIntegration:
    """Integration checks: merging compose.yaml + compose.stub.yaml."""

    def test_both_files_define_app_service(self) -> None:
        """Both compose.yaml and compose.stub.yaml reference the 'app' service."""
        base_path = Path(__file__).resolve().parent / "compose.yaml"
        with base_path.open() as f:
            base = yaml.safe_load(f)
        stub = _load_compose_stub()

        assert "app" in base["services"], "compose.yaml must define 'app'"
        assert "app" in stub["services"], "compose.stub.yaml must override 'app'"

    def test_stub_does_not_redefine_build_for_app(self) -> None:
        """compose.stub.yaml must not redefine app build — only env override."""
        stub = _load_compose_stub()
        app_svc = stub["services"]["app"]
        assert "build" not in app_svc, (
            "compose.stub.yaml must not redefine app build context"
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
