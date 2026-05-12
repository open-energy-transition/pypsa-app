"""Validate tests/e2e/run.sh — driver script with cleanup trap and stub-LLM detection.

The run.sh driver script must:
- set -euo pipefail
- cd to the e2e directory
- define a cleanup function that runs `docker compose down -v --remove-orphans`
- trap EXIT to fire cleanup
- check LLM_API_KEY and conditionally include compose.stub.yaml as an override file
- build + start the app via `docker compose up -d --build --wait`
- iterate test scripts in tests/*.sh, track pass/fail
- exit non-zero if any test fails
- the cleanup trap fires even on test failure
"""

from __future__ import annotations

import stat
import subprocess
import tempfile
from pathlib import Path

RUN_SH_PATH = Path(__file__).resolve().parent / "run.sh"


def _read_run_sh() -> str:
    """Read run.sh content, asserting it exists."""
    if not RUN_SH_PATH.exists():
        msg = f"run.sh not found at {RUN_SH_PATH}"
        raise FileNotFoundError(msg)
    return RUN_SH_PATH.read_text()


class TestRunShExistsAndExecutable:
    """The run.sh file must exist and be executable."""

    def test_file_exists(self) -> None:
        """run.sh exists at tests/e2e/run.sh."""
        assert RUN_SH_PATH.exists(), f"Expected {RUN_SH_PATH} to exist"
        assert RUN_SH_PATH.is_file(), f"Expected {RUN_SH_PATH} to be a file"

    def test_file_is_executable(self) -> None:
        """run.sh must have the executable permission bit set."""
        st = RUN_SH_PATH.stat()
        is_exec = bool(st.st_mode & stat.S_IXUSR)
        assert is_exec, "run.sh must be executable (chmod +x)"


class TestRunShStructure:
    """Validate the structure and required elements of run.sh."""

    def test_shebang_is_bash(self) -> None:
        """Script must start with #!/usr/bin/env bash shebang."""
        content = _read_run_sh()
        first_line = content.split("\n")[0].strip()
        assert first_line == "#!/usr/bin/env bash", (
            f"Expected '#!/usr/bin/env bash', got '{first_line}'"
        )

    def test_set_euo_pipefail(self) -> None:
        """Script must use `set -euo pipefail` for strict error handling."""
        content = _read_run_sh()
        assert "set -euo pipefail" in content, (
            "run.sh must include 'set -euo pipefail'"
        )

    def test_cd_to_script_dir(self) -> None:
        """Script must cd to its own directory."""
        content = _read_run_sh()
        assert 'cd "$(dirname "$0")"' in content, (
            'run.sh must cd to "$(dirname "$0")"'
        )

    def test_cleanup_function_defined(self) -> None:
        """Script must define a cleanup() function."""
        content = _read_run_sh()
        assert "cleanup()" in content, (
            "run.sh must define a cleanup() function"
        )

    def test_cleanup_runs_docker_compose_down(self) -> None:
        """cleanup function must call `docker compose down -v --remove-orphans`."""
        content = _read_run_sh()
        assert "docker compose" in content, (
            "run.sh must invoke docker compose"
        )
        assert "down" in content, (
            "cleanup must run 'docker compose down'"
        )
        assert "-v" in content, (
            "cleanup must include -v to remove volumes"
        )
        assert "--remove-orphans" in content, (
            "cleanup must include --remove-orphans"
        )

    def test_trap_exit_calls_cleanup(self) -> None:
        """Script must trap EXIT to invoke the cleanup function."""
        content = _read_run_sh()
        assert "trap cleanup EXIT" in content, (
            "run.sh must have 'trap cleanup EXIT'"
        )

    def test_docker_compose_up_build_wait(self) -> None:
        """Script must run `docker compose up -d --build --wait`."""
        content = _read_run_sh()
        assert "up -d" in content, (
            "run.sh must use 'docker compose up -d'"
        )
        assert "--build" in content, (
            "run.sh must include --build to rebuild images"
        )
        assert "--wait" in content, (
            "run.sh must include --wait for healthcheck readiness"
        )

    def test_iterates_test_scripts(self) -> None:
        """Script must iterate over tests/*.sh."""
        content = _read_run_sh()
        assert "tests/*.sh" in content, (
            "run.sh must iterate over 'tests/*.sh'"
        )

    def test_tracks_pass_fail(self) -> None:
        """Script must track and report PASS/FAIL counts."""
        content = _read_run_sh()
        assert "PASS" in content, (
            "run.sh must track PASS count"
        )
        assert "FAIL" in content, (
            "run.sh must track FAIL count"
        )

    def test_exits_nonzero_on_failure(self) -> None:
        """Script must exit with non-zero status when any test fails."""
        content = _read_run_sh()
        assert '[ "$FAIL" -eq 0 ]' in content, (
            'run.sh must exit with `[ "$FAIL" -eq 0 ]`'
        )


class TestRunShStubLogic:
    """Validate the LLM_API_KEY detection and compose override logic."""

    def test_contains_docker_compose_command(self) -> None:
        """run.sh must invoke 'docker compose'."""
        content = _read_run_sh()
        assert "docker compose" in content, (
            "run.sh must invoke docker compose"
        )

    def test_contains_compose_yaml_reference(self) -> None:
        """run.sh must reference compose.yaml."""
        content = _read_run_sh()
        assert "compose.yaml" in content, (
            "run.sh must reference compose.yaml"
        )

    def test_checks_llm_api_key_variable(self) -> None:
        """run.sh must check the LLM_API_KEY variable."""
        content = _read_run_sh()
        assert "LLM_API_KEY" in content, (
            "run.sh must reference LLM_API_KEY"
        )

    def test_has_conditional_for_stub_override(self) -> None:
        """run.sh must conditionally include compose.stub.yaml."""
        content = _read_run_sh()
        assert "compose.stub.yaml" in content, (
            "run.sh must reference compose.stub.yaml"
        )

    def test_conditional_uses_z_test_on_llm_api_key(self) -> None:
        """The LLM_API_KEY check must use -z (empty string test) with default."""
        content = _read_run_sh()
        has_empty_check = (
            "${LLM_API_KEY:-}" in content
            or "${LLM_API_KEY" in content
        )
        assert has_empty_check, (
            "run.sh must check LLM_API_KEY emptiness using ${LLM_API_KEY:-}"
        )
        assert "-z" in content, "run.sh must use -z to test for empty LLM_API_KEY"

    def test_on_unset_key_uses_stub_override(self) -> None:
        """When LLM_API_KEY is empty, compose.stub.yaml is included."""
        content = _read_run_sh()
        stub_override_line = None
        for line in content.splitlines():
            if "compose.stub.yaml" in line:
                stub_override_line = line
                break
        assert stub_override_line is not None, (
            "Could not find line with compose.stub.yaml"
        )
        assert "compose.yaml" in stub_override_line, (
            "compose.stub.yaml must be used alongside compose.yaml"
        )
        assert "-f" in stub_override_line, (
            "compose.stub.yaml must be passed with -f flag"
        )


class TestRunShTrapFiresOnFailure:
    """Verify the cleanup trap fires via docker compose down even on failure.

    Creates a sandbox with a fake docker-compose that records invocations,
    a trivial pass test, and a failing test. Verifies that `docker compose down`
    is called despite the test failure (trap fires on EXIT).
    """

    def test_trap_fires_on_test_failure(self) -> None:
        """cleanup trap runs docker compose down even when a test fails."""
        content = _read_run_sh()

        with tempfile.TemporaryDirectory() as sandbox:
            _setup_sandbox(sandbox, content)
            sandbox_path = Path(sandbox)
            run_sh = sandbox_path / "run.sh"
            run_sh.chmod(run_sh.stat().st_mode | stat.S_IXUSR)

            proc = subprocess.run(
                ["bash", str(run_sh)],
                cwd=sandbox,
                capture_output=True,
                text=True,
            )

            log_path = sandbox_path / "dc.log"
            calls = (
                log_path.read_text().strip().splitlines()
                if log_path.exists()
                else []
            )

            down_called = any("down" in c for c in calls)
            assert down_called, (
                f"Expected 'docker compose down' in dc.log, got: {calls}"
            )

            assert proc.returncode != 0, (
                f"Expected non-zero exit due to test failure, got {proc.returncode}"
            )


def _setup_sandbox(sandbox: str, content: str) -> None:
    """Create a sandbox directory with fake docker compose, compose.yaml, and tests."""
    sandbox_path = Path(sandbox)

    dc_log = sandbox_path / "dc.log"
    dc_script = _fake_docker_compose_script(dc_log)

    dc_bin = sandbox_path / "docker"
    dc_bin.write_text(dc_script)
    dc_bin.chmod(dc_bin.stat().st_mode | stat.S_IXUSR)

    adapted = content.replace(
        "docker compose",
        f"{dc_bin} compose",
    )
    run_sh = sandbox_path / "run.sh"
    run_sh.write_text(adapted)

    compose_yaml = sandbox_path / "compose.yaml"
    compose_yaml.write_text("services:\n  app:\n    image: dummy\n")

    tests_dir = sandbox_path / "tests"
    tests_dir.mkdir(exist_ok=True)

    passing = tests_dir / "00_pass.sh"
    passing.write_text("#!/usr/bin/env bash\nset -eu\necho ok\nexit 0\n")
    passing.chmod(passing.stat().st_mode | stat.S_IXUSR)

    failing = tests_dir / "01_fail.sh"
    failing.write_text(
        "#!/usr/bin/env bash\nset -eu\necho 'expected failure'\nexit 1\n"
    )
    failing.chmod(failing.stat().st_mode | stat.S_IXUSR)


def _fake_docker_compose_script(log_path: Path) -> str:
    """Return a fake `docker` script that logs subcommands and does nothing."""
    return f"""#!/usr/bin/env bash
echo "${{*}}" >> {log_path}
if [[ "${{1}}" == "compose" && "${{2}}" == "up" ]]; then
    sleep 0.1
    true
fi
true
"""
