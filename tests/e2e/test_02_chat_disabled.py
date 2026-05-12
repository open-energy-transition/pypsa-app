"""Validate tests/e2e/tests/02_chat_disabled_returns_404.sh.

The test script must bring up the app with CHAT_ENABLED=false,
POST to /api/v1/chat/stream, and assert the response status is 404.
"""

from __future__ import annotations

import stat
from pathlib import Path

TEST_SCRIPT_PATH = (
    Path(__file__).resolve().parent / "tests" / "02_chat_disabled_returns_404.sh"
)


def _read_test_script() -> str:
    """Read the test script content, asserting it exists."""
    if not TEST_SCRIPT_PATH.exists():
        msg = f"Test script not found at {TEST_SCRIPT_PATH}"
        raise FileNotFoundError(msg)
    return TEST_SCRIPT_PATH.read_text()


class TestScriptExistsAndExecutable:
    """The test script must exist and be executable."""

    def test_file_exists(self) -> None:
        """02_chat_disabled_returns_404.sh exists in tests/e2e/tests/."""
        assert TEST_SCRIPT_PATH.exists(), (
            f"Expected {TEST_SCRIPT_PATH} to exist"
        )
        assert TEST_SCRIPT_PATH.is_file(), (
            f"Expected {TEST_SCRIPT_PATH} to be a file"
        )

    def test_file_is_executable(self) -> None:
        """Script must have the executable permission bit set."""
        st = TEST_SCRIPT_PATH.stat()
        is_exec = bool(st.st_mode & stat.S_IXUSR)
        assert is_exec, (
            "02_chat_disabled_returns_404.sh must be executable (chmod +x)"
        )


class TestScriptStructure:
    """Validate the content and structure of the test script."""

    def test_shebang_is_bash(self) -> None:
        """Script must start with #!/usr/bin/env bash shebang."""
        content = _read_test_script()
        first_line = content.split("\n")[0].strip()
        assert first_line == "#!/usr/bin/env bash", (
            f"Expected '#!/usr/bin/env bash', got '{first_line}'"
        )

    def test_set_euo_pipefail(self) -> None:
        """Script must use `set -euo pipefail`."""
        content = _read_test_script()
        assert "set -euo pipefail" in content, (
            "Test script must include 'set -euo pipefail'"
        )

    def test_references_compose_yaml(self) -> None:
        """Script must reference compose.yaml as the base compose file."""
        content = _read_test_script()
        assert "compose.yaml" in content, (
            "Test script must reference compose.yaml"
        )

    def test_references_compose_disabled_yaml(self) -> None:
        """Script must reference compose.disabled.yaml as the override."""
        content = _read_test_script()
        assert "compose.disabled.yaml" in content, (
            "Test script must reference compose.disabled.yaml"
        )

    def test_uses_docker_compose_up(self) -> None:
        """Script must use docker compose up to start the disabled stack."""
        content = _read_test_script()
        assert "docker compose" in content, (
            "Test script must invoke docker compose"
        )
        assert "up" in content, (
            "Test script must use 'docker compose up'"
        )

    def test_uses_docker_compose_down(self) -> None:
        """Script must use docker compose down for cleanup."""
        content = _read_test_script()
        assert "down" in content, (
            "Test script must use 'docker compose down' to tear down"
        )

    def test_has_cleanup_trap(self) -> None:
        """Script must define a cleanup trap to ensure teardown."""
        content = _read_test_script()
        assert "trap" in content, (
            "Test script must have a cleanup trap"
        )
        assert "EXIT" in content, (
            "Cleanup trap must fire on EXIT"
        )

    def test_posts_to_chat_stream_endpoint(self) -> None:
        """Script must POST to /api/v1/chat/stream."""
        content = _read_test_script()
        assert "/api/v1/chat/stream" in content, (
            "Test script must hit /api/v1/chat/stream"
        )

    def test_asserts_404_status(self) -> None:
        """Script must assert the HTTP status is 404."""
        content = _read_test_script()
        assert '"404"' in content or "'404'" in content or "= 404" in content, (
            "Test script must assert status 404"
        )

    def test_uses_curl_for_request(self) -> None:
        """Script must use curl to make the HTTP request."""
        content = _read_test_script()
        assert "curl" in content, (
            "Test script must use curl"
        )

    def test_uses_port_8766(self) -> None:
        """Script must use port 8766 (disabled stack port)."""
        content = _read_test_script()
        assert "8766" in content, (
            "Test script must use port 8766 for the disabled stack"
        )

    def test_exits_with_status_assertion(self) -> None:
        """Script exit status must be determined by the 404 assertion."""
        content = _read_test_script()
        # The last meaningful assertion should check status == 404
        lines = content.splitlines()
        non_empty = [
            line
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
        last_assertion = None
        for line in reversed(non_empty):
            if "404" in line and ("[" in line or "=" in line or "test" in line):
                last_assertion = line
                break
        assert last_assertion is not None, (
            "Test script must have a final assertion checking for 404 status"
        )
