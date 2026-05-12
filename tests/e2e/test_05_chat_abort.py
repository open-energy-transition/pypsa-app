"""Validate tests/e2e/tests/05_chat_abort.sh.

The script must:

- Start a long-running chat stream in the background via curl
- Kill the curl process after a short wait (abort mid-stream)
- Query /api/v1/health after the abort and assert the server is still healthy
- Clean up the background process on exit (trap)
"""

from __future__ import annotations

import socket
import stat
import subprocess
import tempfile
import time
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "tests" / "05_chat_abort.sh"


def _read_script() -> str:
    """Read 05_chat_abort.sh content, asserting it exists."""
    if not SCRIPT_PATH.exists():
        msg = f"05_chat_abort.sh not found at {SCRIPT_PATH}"
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


def _replace_port(content: str, port: int) -> str:
    """Replace the hardcoded port 8765 with the given port."""
    return content.replace("127.0.0.1:8765", f"127.0.0.1:{port}")


class TestScriptExistsAndExecutable:
    """The 05_chat_abort.sh file must exist and be executable."""

    def test_file_exists(self) -> None:
        """05_chat_abort.sh exists at tests/e2e/tests/05_chat_abort.sh."""
        assert SCRIPT_PATH.exists(), f"Expected {SCRIPT_PATH} to exist"
        assert SCRIPT_PATH.is_file(), f"Expected {SCRIPT_PATH} to be a file"

    def test_file_is_executable(self) -> None:
        """05_chat_abort.sh must have the executable permission bit set."""
        st = SCRIPT_PATH.stat()
        is_exec = bool(st.st_mode & stat.S_IXUSR)
        assert is_exec, "05_chat_abort.sh must be executable (chmod +x)"


class TestScriptStructure:
    """Validate the structure and required elements of 05_chat_abort.sh."""

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
            "05_chat_abort.sh must include 'set -euo pipefail'"
        )

    def test_curls_chat_stream_endpoint(self) -> None:
        """Script must curl POST to /api/v1/chat/stream."""
        content = _read_script()
        assert "/api/v1/chat/stream" in content, (
            "05_chat_abort.sh must call /api/v1/chat/stream"
        )

    def test_uses_background_process(self) -> None:
        """Script must run curl in the background (using &)."""
        content = _read_script()
        assert "&" in content, (
            "05_chat_abort.sh must start curl as a background process"
        )

    def test_sleeps_before_kill(self) -> None:
        """Script must sleep for a short period before killing the stream."""
        content = _read_script()
        assert "sleep" in content, (
            "05_chat_abort.sh must sleep before aborting"
        )

    def test_kills_curl_process(self) -> None:
        """Script must kill the background curl process."""
        content = _read_script()
        assert "kill" in content, (
            "05_chat_abort.sh must kill the background curl"
        )

    def test_queries_health_after_abort(self) -> None:
        """Script must query /api/v1/health after aborting the stream."""
        content = _read_script()
        assert "/api/v1/health" in content, (
            "05_chat_abort.sh must query /api/v1/health after abort"
        )

    def test_uses_curl_fail_flag_on_health(self) -> None:
        """Script must use curl -f (or -fs) to fail on health errors."""
        content = _read_script()
        assert "-fs" in content or "-f " in content, (
            "05_chat_abort.sh must use curl -f to fail on HTTP errors"
        )

    def test_has_cleanup_trap(self) -> None:
        """Script must define a cleanup trap for the background process."""
        content = _read_script()
        assert "trap" in content, (
            "05_chat_abort.sh must have a cleanup trap"
        )


class TestScriptFunctional:
    """Functional: script runs against a mock server for chat stream + health."""

    def test_script_exits_zero_after_abort_and_health_ok(self) -> None:
        """Script exits 0 when the server remains healthy after an abort."""
        port = _find_free_port()
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            server_script = _fake_stream_server_script(
                port, health_status=200
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
                script_path = sandbox_path / "05_chat_abort.sh"
                script_path.write_text(adapted)
                script_path.chmod(
                    script_path.stat().st_mode | stat.S_IXUSR
                )

                proc = subprocess.run(
                    ["bash", str(script_path)],
                    cwd=sandbox,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                assert proc.returncode == 0, (
                    f"Expected exit 0 after healthy abort, got {proc.returncode}\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
            finally:
                server_proc.terminate()
                server_proc.wait(timeout=5)

    def test_script_exits_nonzero_when_health_fails_after_abort(self) -> None:
        """Script exits non-zero when health endpoint returns 500 after abort."""
        port = _find_free_port()
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            server_script = _fake_stream_server_script(
                port, health_status=500
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
                script_path = sandbox_path / "05_chat_abort.sh"
                script_path.write_text(adapted)
                script_path.chmod(
                    script_path.stat().st_mode | stat.S_IXUSR
                )

                proc = subprocess.run(
                    ["bash", str(script_path)],
                    cwd=sandbox,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                msg = (
                    "Expected non-zero exit when health fails after abort,"
                    f" got {proc.returncode}\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
                assert proc.returncode != 0, msg
            finally:
                server_proc.terminate()
                server_proc.wait(timeout=5)


def _fake_stream_server_script(port: int, health_status: int = 200) -> str:
    """Return a minimal HTTP server that serves a slow SSE chat stream and health."""
    return f"""
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = {port}

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/v1/chat/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            self.wfile.write(b'event: RunStarted\\n')
            self.wfile.write(b'data: {{"run_id":"r1","model":"stub"}}\\n\\n')
            self.wfile.flush()

            for i in range(20):
                self.wfile.write(b'event: TextMessageContent\\n')
                chunk = f'{{"message_id":"msg1","delta":"chunk{{i}}"}}'
                self.wfile.write(f'data: {{chunk}}\\n\\n'.encode())
                self.wfile.flush()
                time.sleep(0.5)

            self.wfile.write(b'event: RunFinished\\n')
            self.wfile.write(b'data: {{"run_id":"r1","stop_reason":"stop"}}\\n\\n')
            self.wfile.flush()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/api/v1/health":
            self.send_response({health_status})
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{{"status":"ok"}}')
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
