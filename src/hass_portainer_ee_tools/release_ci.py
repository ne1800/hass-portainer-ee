"""Require complete main-branch CI for exactly the release commit."""

import argparse
import json
import re
import subprocess
import sys

from .errors import PortainerToolError

REQUIRED_JOBS = {"Verify", "Test build (amd64)", "Test build (aarch64)"}


def select_ci_run(payload: object, commit: str) -> int:
    try:
        matching = [
            run
            for run in payload["workflow_runs"]
            if run["head_sha"] == commit
            and run["head_branch"] == "main"
            and run["event"] == "push"
            and run["path"] == ".github/workflows/ci.yml"
        ]
        if not matching:
            raise ValueError("no main-branch CI found for this commit")
        latest = max(matching, key=lambda run: (run["run_number"], run["run_attempt"]))
        if latest["status"] != "completed" or latest["conclusion"] != "success":
            raise ValueError("latest CI for this commit has not passed")
        return int(latest["id"])
    except (KeyError, TypeError, ValueError) as error:
        raise PortainerToolError(f"release CI rejected: {error}") from error


def check_ci_jobs(payload: object, commit: str) -> None:
    try:
        jobs = payload["jobs"]
        if len(jobs) != payload["total_count"]:
            raise ValueError("incomplete CI jobs response")
        for name in REQUIRED_JOBS:
            matching = [job for job in jobs if job["name"] == name]
            if len(matching) != 1 or any(
                job["head_sha"] != commit
                or job["status"] != "completed"
                or job["conclusion"] != "success"
                for job in matching
            ):
                raise ValueError(f"required job has not passed: {name}")
    except (KeyError, TypeError, ValueError) as error:
        raise PortainerToolError(f"release CI rejected: {error}") from error


def _get(endpoint: str) -> object:
    try:
        result = subprocess.run(
            ["gh", "api", endpoint], check=True, capture_output=True, text=True
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise PortainerToolError("could not read release CI from GitHub") from error


def release_ci_main() -> int:
    parser = argparse.ArgumentParser(
        description="Require successful CI for a release commit"
    )
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        if re.fullmatch(r"[0-9a-f]{40}", args.commit) is None:
            raise PortainerToolError("commit must be a complete Git SHA")
        base = "repos/ne1800/hass-portainer-ee/actions"
        runs = _get(
            f"{base}/workflows/ci.yml/runs?event=push&branch=main"
            f"&head_sha={args.commit}&per_page=100"
        )
        run_id = select_ci_run(runs, args.commit)
        jobs = _get(f"{base}/runs/{run_id}/jobs?filter=latest&per_page=100")
        check_ci_jobs(jobs, args.commit)
    except PortainerToolError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"CI passed for release commit {args.commit}.")
    return 0
