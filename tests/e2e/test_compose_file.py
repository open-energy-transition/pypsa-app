"""Validate tests/e2e/compose.yaml structure.

The compose file must define a full-stack app service with healthcheck.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_PATH = Path(__file__).resolve().parent / "compose.yaml"


def _load_compose() -> dict:
    """Load and return the compose YAML as a dict."""
    if not COMPOSE_PATH.exists():
        msg = f"compose.yaml not found at {COMPOSE_PATH}"
        raise FileNotFoundError(msg)
    with COMPOSE_PATH.open() as f:
        return yaml.safe_load(f)


class TestComposeExists:
    """The compose.yaml file must exist."""

    def test_file_exists(self) -> None:
        """compose.yaml exists at tests/e2e/compose.yaml."""
        assert COMPOSE_PATH.exists(), f"Expected {COMPOSE_PATH} to exist"
        assert COMPOSE_PATH.is_file(), f"Expected {COMPOSE_PATH} to be a file"


class TestComposeStructure:
    """Validate service definitions and healthcheck."""

    def test_services_section_present(self) -> None:
        """Top-level 'services' key must be present."""
        compose = _load_compose()
        assert "services" in compose, "compose.yaml must have a 'services' section"

    def test_app_service_defined(self) -> None:
        """An 'app' service must be defined."""
        compose = _load_compose()
        assert "app" in compose["services"], "'app' service must be defined"

    def test_build_target_is_full(self) -> None:
        """Build target must be 'full' to include frontend static files."""
        compose = _load_compose()
        build = compose["services"]["app"].get("build", {})
        assert build.get("target") == "full", (
            "build.target must be 'full' to serve static frontend"
        )

    def test_dockerfile_is_root_dockerfile(self) -> None:
        """Dockerfile path must point at the repo root Dockerfile."""
        compose = _load_compose()
        build = compose["services"]["app"].get("build", {})
        assert "dockerfile" in build, "build.dockerfile must be specified"
        assert build["dockerfile"] == "Dockerfile", (
            "build.dockerfile must be the repo-root Dockerfile"
        )

    def test_port_mapping(self) -> None:
        """Port 8000 mapped to 127.0.0.1:8765 for local-only access."""
        compose = _load_compose()
        ports = compose["services"]["app"].get("ports", [])
        expected = "127.0.0.1:8765:8000"
        assert expected in ports, (
            f"ports must include '{expected}' for local-only E2E access"
        )

    def test_extra_hosts_for_docker_internal(self) -> None:
        """extra_hosts must include host.docker.internal for Ollama access."""
        compose = _load_compose()
        extra_hosts = compose["services"]["app"].get("extra_hosts", [])
        expected = "host.docker.internal:host-gateway"
        assert expected in extra_hosts, (
            f"extra_hosts must include '{expected}'"
        )

    def test_healthcheck_defined(self) -> None:
        """Healthcheck must be defined for 'docker compose up --wait'."""
        compose = _load_compose()
        hc = compose["services"]["app"].get("healthcheck", {})
        assert hc, "app service must have a healthcheck"

    def test_healthcheck_uses_curl(self) -> None:
        """Healthcheck must curl /health — the route is bare, not under API_V1_PREFIX."""
        compose = _load_compose()
        hc = compose["services"]["app"].get("healthcheck", {})
        test_cmd = hc.get("test", [])
        assert "CMD" in test_cmd, "healthcheck.test must use CMD form"
        assert "curl" in test_cmd, "healthcheck.test must use curl"
        url_parts = [p for p in test_cmd if p.startswith("http")]
        assert url_parts, f"healthcheck.test must include an http URL, got: {test_cmd}"
        url = url_parts[0]
        assert "/api/v1/health" not in url, (
            f"healthcheck must NOT hit /api/v1/health — that route does not exist; got: {url}"
        )
        assert url.endswith("/health"), (
            f"healthcheck must hit /health (bare), got: {url}"
        )

    def test_healthcheck_timing(self) -> None:
        """Healthcheck must have interval, timeout, and retries set."""
        compose = _load_compose()
        hc = compose["services"]["app"].get("healthcheck", {})
        assert "interval" in hc, "healthcheck must have interval"
        assert "timeout" in hc, "healthcheck must have timeout"
        assert "retries" in hc, "healthcheck must have retries"

    def test_retries_is_at_least_10(self) -> None:
        """Retries must be large enough for slow container startup."""
        compose = _load_compose()
        hc = compose["services"]["app"].get("healthcheck", {})
        retries = hc.get("retries", 0)
        assert retries >= 10, (
            f"healthcheck retries ({retries}) must be >= 10 for slow startup"
        )


class TestComposeEnvironment:
    """Validate required environment variables for the app service."""

    @staticmethod
    def _env_dict(compose: dict) -> dict[str, str]:
        """Parse environment list into a dict for easy lookup."""
        env_list = compose["services"]["app"].get("environment", [])
        if isinstance(env_list, dict):
            return env_list
        result: dict[str, str] = {}
        for item in env_list:
            if "=" in item:
                key, val = item.split("=", 1)
                result[key] = val
        return result

    def test_chat_enabled_true(self) -> None:
        """CHAT_ENABLED must be 'true'."""
        env = self._env_dict(_load_compose())
        assert "CHAT_ENABLED" in env, "CHAT_ENABLED must be set"
        assert env["CHAT_ENABLED"] == "true", (
            f"CHAT_ENABLED must be 'true', got '{env['CHAT_ENABLED']}'"
        )

    def test_llm_provider_set(self) -> None:
        """LLM_PROVIDER must be set (defaults to openai)."""
        env = self._env_dict(_load_compose())
        assert "LLM_PROVIDER" in env, "LLM_PROVIDER must be set"

    def test_llm_model_uses_env_var_substitution(self) -> None:
        """LLM_MODEL should use ${LLM_MODEL:-...} substitution."""
        env = self._env_dict(_load_compose())
        model_value = env.get("LLM_MODEL", "")
        assert model_value, "LLM_MODEL must be set"
        assert "${LLM_MODEL" in model_value, (
            "LLM_MODEL should use ${LLM_MODEL:-...} to allow override"
        )

    def test_auth_enabled_false(self) -> None:
        """AUTH_ENABLED must be 'false' for E2E harness."""
        env = self._env_dict(_load_compose())
        assert "AUTH_ENABLED" in env, "AUTH_ENABLED must be set"
        assert env["AUTH_ENABLED"].lower() in ("false", "0"), (
            f"AUTH_ENABLED must be false, got '{env['AUTH_ENABLED']}'"
        )

    def test_database_url_set(self) -> None:
        """DATABASE_URL must be set (SQLite for E2E)."""
        env = self._env_dict(_load_compose())
        assert "DATABASE_URL" in env, "DATABASE_URL must be set"
        assert "sqlite" in env["DATABASE_URL"], (
            "DATABASE_URL should use SQLite for E2E test harness"
        )
