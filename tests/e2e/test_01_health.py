"""Validate tests/e2e/tests/01_health.sh — health-check E2E test script.

The script must:
- have a bash shebang
- set -euo pipefail
- query GET /api/v1/health and succeed (exit 0)
- query GET /api/v1/version/ and assert chat_enabled is true
"""

from __future__ import annotations

import socket
import stat
import subprocess
import tempfile
import time
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "tests" / "01_health.sh"


def _read_script() -> str:
    """Read 01_health.sh content, asserting it exists."""
    if not SCRIPT_PATH.exists():
        msg = f"01_health.sh not found at {SCRIPT_PATH}"
        raise FileNotFoundError(msg)
    return SCRIPT_PATH.read_text()


def _find_free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout_s: float = 5.0) -> None:
    """Block until a TCP server is accepting connections, or raise."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.05)
    msg = f"Fake server on 127.0.0.1:{port} did not start in {timeout_s}s"
    raise AssertionError(msg)


class TestHealthScriptExistsAndExecutable:
    """The 01_health.sh file must exist and be executable."""

    def test_file_exists(self) -> None:
        """01_health.sh exists at tests/e2e/tests/01_health.sh."""
        assert SCRIPT_PATH.exists(), f"Expected {SCRIPT_PATH} to exist"
        assert SCRIPT_PATH.is_file(), f"Expected {SCRIPT_PATH} to be a file"

    def test_file_is_executable(self) -> None:
        """01_health.sh must have the executable permission bit set."""
        st = SCRIPT_PATH.stat()
        is_exec = bool(st.st_mode & stat.S_IXUSR)
        assert is_exec, "01_health.sh must be executable (chmod +x)"


class TestHealthScriptStructure:
    """Validate the structure and required elements of 01_health.sh."""

    def test_shebang_is_bash(self) -> None:
        """Script must start with #!/usr/bin/env bash shebang."""
        content = _read_script()
        first_line = content.split("\n")[0].strip()
        assert first_line == "#!/usr/bin/env bash", (
            f"Expected '#!/usr/bin/env bash', got '{first_line}'"
        )

    def test_set_euo_pipefail(self) -> None:
        """Script must use `set -euo pipefail` for strict error handling."""
        content = _read_script()
        assert "set -euo pipefail" in content, (
            "01_health.sh must include 'set -euo pipefail'"
        )

    def test_curls_health_endpoint(self) -> None:
        """Script must curl the /api/v1/health endpoint and succeed."""
        content = _read_script()
        assert "/api/v1/health" in content, (
            "01_health.sh must curl /api/v1/health"
        )
        assert "curl" in content, (
            "01_health.sh must invoke curl"
        )
        assert "-fs" in content or "-f" in content, (
            "01_health.sh must use curl -f (fail on HTTP errors)"
        )

    def test_curls_version_endpoint(self) -> None:
        """Script must curl the /api/v1/version/ endpoint."""
        content = _read_script()
        assert "/api/v1/version" in content, (
            "01_health.sh must curl /api/v1/version/"
        )

    def test_asserts_chat_enabled_true(self) -> None:
        """Script must grep for chat_enabled:true in version response."""
        content = _read_script()
        assert '"chat_enabled":true' in content, (
            '01_health.sh must check for \"chat_enabled\":true'
        )
        assert "grep" in content, (
            "01_health.sh must use grep to check version response"
        )


class TestHealthScriptExecution:
    """Verify the script runs correctly against a mock HTTP server."""

    def test_script_exits_zero_on_healthy_server(self) -> None:
        """Script exits 0 when both health and version endpoints respond correctly."""
        port = _find_free_port()
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)
            server_script = _fake_health_server_script(
                port, health_status=200, version_body='{"chat_enabled":true}'
            )
            server_path = sandbox_path / "server.py"
            server_path.write_text(server_script)

            server_proc = subprocess.Popen(
                ["python3", "-u", str(server_path)],
                cwd=sandbox,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _wait_for_server(port)

            try:
                adapted = _replace_port(content, port)
                script_path = sandbox_path / "01_health.sh"
                script_path.write_text(adapted)
                script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)

                proc = subprocess.run(
                    ["bash", str(script_path)],
                    cwd=sandbox,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                assert proc.returncode == 0, (
                    f"Expected exit 0 from healthy server, got {proc.returncode}\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
            finally:
                server_proc.terminate()
                server_proc.wait(timeout=5)

    def test_script_exits_nonzero_when_health_fails(self) -> None:
        """Script exits non-zero when the health endpoint returns 5xx."""
        port = _find_free_port()
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)
            server_script = _fake_health_server_script(port, health_status=500)
            server_path = sandbox_path / "server.py"
            server_path.write_text(server_script)

            server_proc = subprocess.Popen(
                ["python3", "-u", str(server_path)],
                cwd=sandbox,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _wait_for_server(port)

            try:
                adapted = _replace_port(content, port)
                script_path = sandbox_path / "01_health.sh"
                script_path.write_text(adapted)
                script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)

                proc = subprocess.run(
                    ["bash", str(script_path)],
                    cwd=sandbox,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                assert proc.returncode != 0, (
                    f"Expected non-zero exit when health fails, got {proc.returncode}\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
            finally:
                server_proc.terminate()
                server_proc.wait(timeout=5)

    def test_script_exits_nonzero_when_version_missing_chat_enabled(self) -> None:
        """Script exits non-zero when chat_enabled is false."""
        port = _find_free_port()
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)
            server_script = _fake_health_server_script(
                port, health_status=200, version_body='{"chat_enabled":false}'
            )
            server_path = sandbox_path / "server.py"
            server_path.write_text(server_script)

            server_proc = subprocess.Popen(
                ["python3", "-u", str(server_path)],
                cwd=sandbox,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _wait_for_server(port)

            try:
                adapted = _replace_port(content, port)
                script_path = sandbox_path / "01_health.sh"
                script_path.write_text(adapted)
                script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)

                proc = subprocess.run(
                    ["bash", str(script_path)],
                    cwd=sandbox,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                assert proc.returncode != 0, (
                    "Expected non-zero exit when chat_enabled is false,"
                    f" got {proc.returncode}\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
            finally:
                server_proc.terminate()
                server_proc.wait(timeout=5)


def _replace_port(content: str, port: int) -> str:
    """Replace the hardcoded port 8765 with the given port."""
    return content.replace("127.0.0.1:8765", f"127.0.0.1:{port}")


def _fake_health_server_script(
    port: int,
    health_status: int = 200,
    version_body: str = '{"chat_enabled":true}',
) -> str:
    """Return a minimal HTTP server script that serves mock health + version."""
    return f"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = {port}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/health":
            self.send_response({health_status})
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{{"status":"ok"}}')
        elif self.path == "/api/v1/version/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write({version_body!r}.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

import socketserver
class ReusableServer(HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

server = ReusableServer(("127.0.0.1", PORT), Handler)
server.serve_forever()
"""
