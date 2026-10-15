from copy import deepcopy

import pytest

from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.release_ci import (
    REQUIRED_JOBS,
    check_ci_jobs,
    select_ci_run,
)

COMMIT = "a" * 40


def run() -> dict:
    return {
        "id": 7,
        "head_sha": COMMIT,
        "head_branch": "main",
        "event": "push",
        "path": ".github/workflows/ci.yml",
        "run_number": 1,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
    }


def jobs() -> dict:
    return {
        "total_count": len(REQUIRED_JOBS),
        "jobs": [
            {
                "name": name,
                "head_sha": COMMIT,
                "status": "completed",
                "conclusion": "success",
            }
            for name in sorted(REQUIRED_JOBS)
        ],
    }


def test_complete_ci_is_accepted() -> None:
    assert select_ci_run({"workflow_runs": [run()]}, COMMIT) == 7
    check_ci_jobs(jobs(), COMMIT)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("head_sha", "b" * 40),
        ("head_branch", "feature"),
        ("event", "pull_request"),
        ("path", ".github/workflows/other.yml"),
        ("conclusion", "failure"),
        ("status", "in_progress"),
    ],
)
def test_wrong_or_incomplete_ci_is_rejected(key: str, value: str) -> None:
    value_run = run()
    value_run[key] = value
    with pytest.raises(PortainerToolError):
        select_ci_run({"workflow_runs": [value_run]}, COMMIT)


def test_latest_attempt_must_pass() -> None:
    newer = deepcopy(run())
    newer.update(run_attempt=2, conclusion="failure")
    with pytest.raises(PortainerToolError, match="latest CI"):
        select_ci_run({"workflow_runs": [run(), newer]}, COMMIT)


@pytest.mark.parametrize("change", ["missing", "failed", "wrong_commit", "truncated"])
def test_incomplete_jobs_are_rejected(change: str) -> None:
    payload = jobs()
    if change == "missing":
        payload["jobs"].pop()
        payload["total_count"] -= 1
    elif change == "failed":
        payload["jobs"][0]["conclusion"] = "failure"
    elif change == "wrong_commit":
        payload["jobs"][0]["head_sha"] = "b" * 40
    else:
        payload["total_count"] += 1
    with pytest.raises(PortainerToolError):
        check_ci_jobs(payload, COMMIT)
