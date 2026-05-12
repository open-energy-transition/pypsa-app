"""Validate tests/e2e/tests/04_chat_tool_call_list_networks.sh.

The script must:

- Send a curl POST to /api/v1/chat/stream with a prompt that triggers
  the stub LLM to respond with a list_networks tool call
- Pipe the SSE stream through python3 lib/sse_parse.py
- Assert: at least one ToolCallStart with tool_name=="list_networks"
- Assert: at least one ToolCallEnd
- Assert: at least one ToolCallResult with is_error==false
- Print descriptive error messages on assertion failure
- Exit non-zero on any assertion failure
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent / "tests" / "04_chat_tool_call_list_networks.sh"
)


def _read_script() -> str:
    """Read the script content, asserting it exists."""
    if not SCRIPT_PATH.exists():
        msg = f"04_chat_tool_call_list_networks.sh not found at {SCRIPT_PATH}"
        raise FileNotFoundError(msg)
    return SCRIPT_PATH.read_text()


class TestScriptExists:
    """The 04_chat_tool_call_list_networks.sh file must exist and be executable."""

    def test_file_exists(self) -> None:
        """Script exists at tests/e2e/tests/04_chat_tool_call_list_networks.sh."""
        assert SCRIPT_PATH.exists(), f"Expected {SCRIPT_PATH} to exist"
        assert SCRIPT_PATH.is_file(), f"Expected {SCRIPT_PATH} to be a file"

    def test_file_is_executable(self) -> None:
        """Script must have the executable permission bit set."""
        st = SCRIPT_PATH.stat()
        is_exec = bool(st.st_mode & stat.S_IXUSR)
        assert is_exec, "Script must be executable (chmod +x)"


class TestScriptStructure:
    """Validate the structure and required elements of the script."""

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
            "Script must include 'set -euo pipefail'"
        )

    def test_curl_post_to_chat_stream(self) -> None:
        """Script must curl POST to /api/v1/chat/stream."""
        content = _read_script()
        assert "/api/v1/chat/stream" in content, (
            "Script must call /api/v1/chat/stream"
        )

    def test_curl_uses_no_buffer_flag(self) -> None:
        """Script must use curl -N (--no-buffer) for SSE streaming."""
        content = _read_script()
        assert "curl" in content, "Script must use curl"
        has_no_buffer = (
            "-fsN" in content
            or "-N " in content
            or "--no-buffer" in content
        )
        assert has_no_buffer, "curl must use -N/--no-buffer (or -fsN) for SSE"

    def test_pipes_to_sse_parse_py(self) -> None:
        """Script must pipe curl output through python3 lib/sse_parse.py."""
        content = _read_script()
        assert "lib/sse_parse.py" in content, (
            "Script must pipe through lib/sse_parse.py"
        )

    def test_collects_events_via_jq_s(self) -> None:
        """Script must use jq -s to slurp events into an array."""
        content = _read_script()
        assert "jq -s" in content, (
            "Script must use jq -s to collect events into an array"
        )

    def test_asserts_tool_call_start_with_list_networks(self) -> None:
        """Script must assert ToolCallStart with tool_name list_networks."""
        content = _read_script()
        assert "ToolCallStart" in content, (
            "Script must assert ToolCallStart event"
        )
        assert "list_networks" in content, (
            "Script must assert tool_name is list_networks"
        )

    def test_asserts_tool_call_end(self) -> None:
        """Script must assert at least one ToolCallEnd event."""
        content = _read_script()
        assert "ToolCallEnd" in content, (
            "Script must assert ToolCallEnd event"
        )

    def test_asserts_tool_call_result_not_error(self) -> None:
        """Script must assert ToolCallResult with is_error==false."""
        content = _read_script()
        assert "ToolCallResult" in content, (
            "Script must assert ToolCallResult event"
        )
        assert "is_error" in content, (
            "Script must check is_error flag"
        )

    def test_error_message_on_tool_call_start_failure(self) -> None:
        """Script must print error when ToolCallStart assertion fails."""
        content = _read_script()
        assert (
            "expected at least one toolcallstart" in content.lower()
            or (
                "toolcallstart" in content.lower()
                and "expected" in content.lower()
            )
        ), "Script must print error message on ToolCallStart assertion failure"

    def test_error_message_on_tool_call_end_failure(self) -> None:
        """Script must print error when ToolCallEnd assertion fails."""
        content = _read_script()
        assert (
            "expected at least one toolcallend" in content.lower()
            or (
                "toolcallend" in content.lower()
                and "expected" in content.lower()
            )
        ), "Script must print error message on ToolCallEnd assertion failure"

    def test_error_message_on_tool_call_result_failure(self) -> None:
        """Script must print error when ToolCallResult assertion fails."""
        content = _read_script()
        assert (
            "expected at least one toolcallresult" in content.lower()
            or (
                "toolcallresult" in content.lower()
                and "expected" in content.lower()
            )
        ), "Script must print error message on ToolCallResult assertion failure"


class TestScriptFunctional:
    """Functional: script processes a real SSE fixture via real jq."""

    def test_script_passes_against_valid_tool_call_sse_fixture(self) -> None:
        """Script exits 0 when fed a valid SSE stream with tool-call events."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_VALID_TOOL_CALL)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "04.sh"
            script.write_text(adapted)
            script.chmod(script.stat().st_mode | stat.S_IXUSR)

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=sandbox,
                capture_output=True,
                text=True,
            )

            assert proc.returncode == 0, (
                f"Expected exit 0, got {proc.returncode}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )

    def test_script_fails_when_no_tool_call_start(self) -> None:
        """Script exits non-zero when the SSE stream has no ToolCallStart."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_NO_TOOL_CALL_START)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "04.sh"
            script.write_text(adapted)
            script.chmod(script.stat().st_mode | stat.S_IXUSR)

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=sandbox,
                capture_output=True,
                text=True,
            )

            assert proc.returncode != 0, (
                f"Expected non-zero exit, got {proc.returncode}"
            )

    def test_script_fails_when_no_tool_call_end(self) -> None:
        """Script exits non-zero when the SSE stream has no ToolCallEnd."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_NO_TOOL_CALL_END)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "04.sh"
            script.write_text(adapted)
            script.chmod(script.stat().st_mode | stat.S_IXUSR)

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=sandbox,
                capture_output=True,
                text=True,
            )

            assert proc.returncode != 0, (
                f"Expected non-zero exit, got {proc.returncode}"
            )

    def test_script_fails_when_tool_call_result_is_error(self) -> None:
        """Script exits non-zero when all ToolCallResult have is_error==true."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_TOOL_RESULT_ERROR)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "04.sh"
            script.write_text(adapted)
            script.chmod(script.stat().st_mode | stat.S_IXUSR)

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=sandbox,
                capture_output=True,
                text=True,
            )

            assert proc.returncode != 0, (
                f"Expected non-zero exit, got {proc.returncode}"
            )


_RESULT_OK = '{"tool_call_id":"call_abc","result":{"ok":true},'
_RESULT_OK += '"is_error":false,"error":null}'
_FINISHED = '{"run_id":"r1","usage":{"in":0,"out":0},"stop_reason":"end_turn"}'
_RESULT_ERR = '{"tool_call_id":"call_abc","result":null,'
_RESULT_ERR += '"is_error":true,"error":"internal error"}'

_FAKE_CURL_VALID_TOOL_CALL = f"""#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {{"run_id":"r1","model":"stub/qwen3.5:9b"}}

event: ToolCallStart
data: {{"tool_call_id":"call_abc","tool_name":"list_networks"}}

event: ToolCallArgs
data: {{"tool_call_id":"call_abc","delta":"{{\\"limit\\": 10}}"}}

event: ToolCallEnd
data: {{"tool_call_id":"call_abc","args":{{"limit":10}}}}

event: ToolCallResult
data: {_RESULT_OK}

event: RunFinished
data: {_FINISHED}

SSE
"""

_FAKE_CURL_NO_TOOL_CALL_START = f"""#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {{"run_id":"r1","model":"stub/qwen3.5:9b"}}

event: ToolCallArgs
data: {{"tool_call_id":"call_abc","delta":"{{\\"limit\\": 10}}"}}

event: ToolCallEnd
data: {{"tool_call_id":"call_abc","args":{{"limit":10}}}}

event: ToolCallResult
data: {_RESULT_OK}

event: RunFinished
data: {_FINISHED}

SSE
"""

_FAKE_CURL_NO_TOOL_CALL_END = f"""#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {{"run_id":"r1","model":"stub/qwen3.5:9b"}}

event: ToolCallStart
data: {{"tool_call_id":"call_abc","tool_name":"list_networks"}}

event: ToolCallArgs
data: {{"tool_call_id":"call_abc","delta":"{{\\"limit\\": 10}}"}}

event: ToolCallResult
data: {_RESULT_OK}

event: RunFinished
data: {_FINISHED}

SSE
"""

_FAKE_CURL_TOOL_RESULT_ERROR = f"""#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {{"run_id":"r1","model":"stub/qwen3.5:9b"}}

event: ToolCallStart
data: {{"tool_call_id":"call_abc","tool_name":"list_networks"}}

event: ToolCallArgs
data: {{"tool_call_id":"call_abc","delta":"{{\\"limit\\": 10}}"}}

event: ToolCallEnd
data: {{"tool_call_id":"call_abc","args":{{"limit":10}}}}

event: ToolCallResult
data: {_RESULT_ERR}

event: RunFinished
data: {_FINISHED}

SSE
"""


def _patch_script(content: str, sandbox: Path) -> str:
    """Patch the script to use sandbox-local curl binary and real python."""
    adapted = content
    adapted = adapted.replace("curl ", f"{sandbox / 'curl'} ")
    adapted = adapted.replace("curl\n", f"{sandbox / 'curl'}\n")
    adapted = adapted.replace("python3 ", f"{sys.executable} ")
    return adapted
