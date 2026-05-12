"""Validate .github/workflows/e2e.yml — CI workflow that runs run.sh against stub-LLM.

The e2e.yml workflow must:
- Define a workflow job that runs tests/e2e/run.sh
- Not set LLM_API_KEY, so the harness uses the stub-LLM override
- Trigger on push, pull_request, and workflow_dispatch
- Use ubuntu-latest runner with docker compose support
- Include a checkout step
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".github" / "workflows" / "e2e.yml"
)


def _load_workflow() -> dict:
    """Load and return the e2e.yml workflow as a dict."""
    if not WORKFLOW_PATH.exists():
        msg = f"e2e.yml not found at {WORKFLOW_PATH}"
        raise FileNotFoundError(msg)
    with WORKFLOW_PATH.open() as f:
        return yaml.safe_load(f)


class TestE2eWorkflowExists:
    """The e2e.yml workflow file must exist."""

    def test_file_exists(self) -> None:
        """e2e.yml exists at .github/workflows/e2e.yml."""
        assert WORKFLOW_PATH.exists(), f"Expected {WORKFLOW_PATH} to exist"
        assert WORKFLOW_PATH.is_file(), f"Expected {WORKFLOW_PATH} to be a file"


class TestE2eWorkflowTriggers:
    """Validate the workflow trigger events."""

    def test_has_on_section(self) -> None:
        """Workflow must have an 'on' trigger section."""
        wf = _load_workflow()
        assert "on" in wf, "e2e.yml must have an 'on' section"

    def test_triggers_on_push(self) -> None:
        """Workflow must trigger on push events."""
        wf = _load_workflow()
        on_section = wf["on"]
        triggers = _normalize_triggers(on_section)
        assert "push" in triggers, (
            f"e2e.yml must trigger on push, got triggers: {triggers}"
        )

    def test_triggers_on_pull_request(self) -> None:
        """Workflow must trigger on pull_request events."""
        wf = _load_workflow()
        on_section = wf["on"]
        triggers = _normalize_triggers(on_section)
        assert "pull_request" in triggers, (
            f"e2e.yml must trigger on pull_request, got triggers: {triggers}"
        )

    def test_triggers_on_workflow_dispatch(self) -> None:
        """Workflow must support manual trigger via workflow_dispatch."""
        wf = _load_workflow()
        on_section = wf["on"]
        triggers = _normalize_triggers(on_section)
        assert "workflow_dispatch" in triggers, (
            f"e2e.yml must support workflow_dispatch, got triggers: {triggers}"
        )


class TestE2eWorkflowJobs:
    """Validate the workflow job definitions."""

    def test_has_jobs_section(self) -> None:
        """Workflow must have a 'jobs' section."""
        wf = _load_workflow()
        assert "jobs" in wf, "e2e.yml must have a 'jobs' section"

    def test_has_e2e_job(self) -> None:
        """Workflow must define an e2e-tests job (or equivalent)."""
        wf = _load_workflow()
        jobs = wf["jobs"]
        job_names = list(jobs.keys())
        has_e2e_job = any("e2e" in name.lower() for name in job_names)
        assert has_e2e_job, (
            f"e2e.yml must have an e2e-related job, got jobs: {job_names}"
        )

    def test_runs_on_ubuntu_latest(self) -> None:
        """Job must run on ubuntu-latest for Docker Compose support."""
        wf = _load_workflow()
        for job in wf["jobs"].values():
            runner = job.get("runs-on", "")
            assert "ubuntu" in str(runner).lower(), (
                f"Job must run on ubuntu, got runs-on: {runner}"
            )

    def test_has_checkout_step(self) -> None:
        """Workflow must include a checkout step."""
        wf = _load_workflow()
        for job in wf["jobs"].values():
            steps = job.get("steps", [])
            has_checkout = any(
                "checkout" in str(step.get("uses", "")).lower()
                for step in steps
            )
            assert has_checkout, "e2e.yml must include actions/checkout step"

    def test_runs_run_sh_script(self) -> None:
        """Workflow must invoke tests/e2e/run.sh."""
        wf = _load_workflow()
        for job in wf["jobs"].values():
            steps = job.get("steps", [])
            run_sh_found = False
            for step in steps:
                run_cmd = step.get("run", "")
                if "run.sh" in str(run_cmd):
                    run_sh_found = True
                    break
            assert run_sh_found, (
                "e2e.yml must run tests/e2e/run.sh in a step"
            )

    def test_does_not_set_llm_api_key(self) -> None:
        """Workflow must NOT set LLM_API_KEY so stub-LLM path is used.

        The run.sh harness checks whether LLM_API_KEY is empty; if so,
        it brings up the stub-LLM container alongside the app. This
        workflow must use that path, so it must not define LLM_API_KEY
        in env or step-level env.
        """
        wf = _load_workflow()
        wf_str = yaml.dump(wf)
        llm_key_found = "LLM_API_KEY" in wf_str
        assert not llm_key_found, (
            "e2e.yml must NOT set LLM_API_KEY — stub-LLM path requires it unset"
        )

    def test_has_name_field(self) -> None:
        """Workflow must have a 'name' field."""
        wf = _load_workflow()
        assert "name" in wf, "e2e.yml must have a 'name' field"


def _normalize_triggers(on_section: object) -> list[str]:
    """Normalize the 'on' section into a list of trigger event names.

    Handles:
    - list: ["push", "pull_request"]
    - dict: {"push": {...}, "pull_request": null}
    - string: "push" (single event)
    """
    if isinstance(on_section, list):
        triggers: list[str] = []
        for item in on_section:
            if isinstance(item, str):
                triggers.append(item)
            elif isinstance(item, dict):
                triggers.extend(item.keys())
        return triggers
    if isinstance(on_section, dict):
        return list(on_section.keys())
    if isinstance(on_section, str):
        return [on_section]
    return []
