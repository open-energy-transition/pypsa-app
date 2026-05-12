"""Validate tests/e2e/tests/03_chat_enabled_basic_stream.sh.

The script must:

- Send a curl POST to /api/v1/chat/stream with a test message
- Pipe the SSE stream through python3 lib/sse_parse.py
- Assert: first event is RunStarted
- Assert: at least one TextMessageContent event
- Assert: exactly one RunFinished event
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
    Path(__file__).resolve().parent / "tests" / "03_chat_enabled_basic_stream.sh"
)


def _read_script() -> str:
    """Read the script content, asserting it exists."""
    if not SCRIPT_PATH.exists():
        msg = f"03_chat_enabled_basic_stream.sh not found at {SCRIPT_PATH}"
        raise FileNotFoundError(msg)
    return SCRIPT_PATH.read_text()


class TestScriptExists:
    """The 03_chat_enabled_basic_stream.sh file must exist and be executable."""

    def test_file_exists(self) -> None:
        """Script exists at tests/e2e/tests/03_chat_enabled_basic_stream.sh."""
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

    def test_asserts_run_started_is_first_event(self) -> None:
        """Script must assert the first event is RunStarted."""
        content = _read_script()
        assert "RunStarted" in content, (
            "Script must assert first event is RunStarted"
        )

    def test_asserts_at_least_one_text_message_content(self) -> None:
        """Script must assert at least one TextMessageContent event."""
        content = _read_script()
        assert "TextMessageContent" in content, (
            "Script must assert at least one TextMessageContent event"
        )

    def test_asserts_exactly_one_run_finished(self) -> None:
        """Script must assert exactly one RunFinished event."""
        content = _read_script()
        assert "RunFinished" in content, (
            "Script must assert exactly one RunFinished event"
        )

    def test_error_message_on_run_started_failure(self) -> None:
        """Script must print an error message when RunStarted assertion fails."""
        content = _read_script()
        assert "expected first event runstarted" in content.lower() or (
            "runstarted" in content.lower() and "expected" in content.lower()
        ), "Script must print error message on RunStarted assertion failure"

    def test_error_message_on_text_content_failure(self) -> None:
        """Script must print error when TextMessageContent assertion fails."""
        content = _read_script()
        assert (
            "expected at least one textmessagecontent" in content.lower()
            or (
                "textmessagecontent" in content.lower()
                and "expected" in content.lower()
            )
        ), "Script must print error message on TextMessageContent assertion failure"

    def test_error_message_on_run_finished_failure(self) -> None:
        """Script must print an error message when RunFinished assertion fails."""
        content = _read_script()
        assert (
            "expected exactly one runfinished" in content.lower()
            or (
                "runfinished" in content.lower()
                and "expected" in content.lower()
            )
        ), "Script must print error message on RunFinished assertion failure"


class TestScriptFunctional:
    """Functional: script processes a real SSE fixture via real jq."""

    def test_script_passes_against_valid_sse_fixture(self) -> None:
        """Script exits 0 when fed a valid SSE event stream."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_VALID)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "03.sh"
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

    def test_script_fails_when_no_run_started(self) -> None:
        """Script exits non-zero when the SSE stream has no RunStarted event."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_NO_RUN_STARTED)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "03.sh"
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

    def test_script_fails_when_no_text_message_content(self) -> None:
        """Script exits non-zero when the SSE stream has no TextMessageContent."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_NO_TEXT_CONTENT)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "03.sh"
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

    def test_script_fails_when_no_run_finished(self) -> None:
        """Script exits non-zero when the SSE stream has no RunFinished."""
        content = _read_script()

        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)

            lib_dir = sandbox_path / "lib"
            lib_dir.mkdir(parents=True)
            src_parser = Path(__file__).resolve().parent / "lib" / "sse_parse.py"
            shutil.copy(src_parser, lib_dir / "sse_parse.py")

            fake_curl = sandbox_path / "curl"
            fake_curl.write_text(_FAKE_CURL_NO_RUN_FINISHED)
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

            adapted = _patch_script(content, sandbox_path)
            script = sandbox_path / "03.sh"
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


_FAKE_CURL_VALID = """#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {"run_id":"r1","model":"stub/qwen3.5:9b"}

event: TextMessageContent
data: {"message_id":"msg1","delta":"Hello"}

event: TextMessageContent
data: {"message_id":"msg1","delta":" world"}

event: RunFinished
data: {"run_id":"r1","usage":{"total_tokens":10},"stop_reason":"stop"}

SSE
"""

_FAKE_CURL_NO_RUN_STARTED = """#!/usr/bin/env bash
cat <<'SSE'
event: TextMessageContent
data: {"message_id":"msg1","delta":"Hello"}

event: RunFinished
data: {"run_id":"r1","usage":{"total_tokens":5},"stop_reason":"stop"}

SSE
"""

_FAKE_CURL_NO_TEXT_CONTENT = """#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {"run_id":"r1","model":"stub"}

event: RunFinished
data: {"run_id":"r1","usage":{"total_tokens":1},"stop_reason":"stop"}

SSE
"""

_FAKE_CURL_NO_RUN_FINISHED = """#!/usr/bin/env bash
cat <<'SSE'
event: RunStarted
data: {"run_id":"r1","model":"stub"}

event: TextMessageContent
data: {"message_id":"msg1","delta":"Hello"}

SSE
"""


def _patch_script(content: str, sandbox: Path) -> str:
    """Patch the script to use sandbox-local curl binary and real python.

    jq is left as-is — the host's real jq is used for functional tests.
    """
    adapted = content
    adapted = adapted.replace("curl ", f"{sandbox / 'curl'} ")
    adapted = adapted.replace("curl\n", f"{sandbox / 'curl'}\n")
    adapted = adapted.replace("python3 ", f"{sys.executable} ")
    return adapted
