import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hass_portainer_ee_tools.yaml_io import load_yaml

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"update_available": False}, 0),
        ({"update_available": "false"}, 1),
        ({"update_available": None}, 1),
        ({}, 1),
    ],
)
def test_update_workflow_boolean(
    tmp_path: Path, payload: object, expected_status: int
) -> None:
    workflow = load_yaml(ROOT / ".github/workflows/portainer-update.yml")
    step = next(
        s for s in workflow["jobs"]["update"]["steps"] if s.get("id") == "check"
    )
    stub = tmp_path / "mise"
    stub.write_text('#!/bin/sh\ncat "$RUNNER_TEMP/response.json"\n')
    stub.chmod(0o755)
    (tmp_path / "response.json").write_text(json.dumps(payload))
    output = tmp_path / "output"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(output),
    }

    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert (result.returncode == 0) == (expected_status == 0), result.stderr
    if expected_status == 0:
        assert output.read_text() == "update_available=false\n"


def test_update_workflow_preserves_manual_review_commits(tmp_path: Path) -> None:
    workflow = load_yaml(ROOT / ".github/workflows/portainer-update.yml")
    step = next(
        s for s in workflow["jobs"]["update"]["steps"] if s.get("id") == "pull-request"
    )
    commands = tmp_path / "bin"
    commands.mkdir()
    gh = commands / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        + """
import json, os, pathlib, sys
args = sys.argv[1:]
state = pathlib.Path(os.environ['PR_STATE'])
if args[:2] == ['auth', 'setup-git']:
    pass
elif args[:2] == ['pr', 'list']:
    print('1' if state.exists() else '')
elif args[:2] in (['pr', 'create'], ['pr', 'edit']):
    body = pathlib.Path(args[args.index('--body-file') + 1]).read_text()
    payload = {'title': args[args.index('--title') + 1], 'body': body}
    state.write_text(json.dumps(payload))
    print('https://github.com/example/test/pull/1')
elif args[:2] == ['pr', 'view']:
    print(state.read_text())
else:
    raise SystemExit('Unexpected GitHub CLI command')
"""
    )
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_REPOSITORY": "example/test",
        "TARGET_VERSION": "9.0.0",
        "TARGET_CHANNEL": "STS",
        "APP_VERSION": "9.0.0.1",
        "UPDATE_REASON": "newer_sts",
        "SERVER_DIGEST": "sha256:" + "a" * 64,
        "AGENT_DIGEST": "sha256:" + "b" * 64,
        "RELEASE_URL": "https://github.com/portainer/portainer/releases/tag/9.0.0",
        "PR_STATE": str(tmp_path / "pr.json"),
    }

    def git(root: Path, *args: str) -> str:
        return subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", "--quiet", "--initial-branch=main", str(remote))
    initial = tmp_path / "initial"
    git(tmp_path, "init", "--quiet", "--initial-branch=main", str(initial))
    (initial / "release.yaml").write_text("base\n")
    git(initial, "add", ".")
    git(
        initial,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "test: base",
    )
    git(initial, "remote", "add", "origin", str(remote))
    git(initial, "push", "--quiet", "origin", "main")

    def run_update(name: str) -> subprocess.CompletedProcess[str]:
        root = tmp_path / name
        git(tmp_path, "clone", "--quiet", "--branch", "main", str(remote), str(root))
        git(root, "config", "core.hooksPath", "/dev/null")
        git(root, "config", "commit.gpgsign", "false")
        (root / "release.yaml").write_text("updated\n")
        # Match the paths always created by update:apply.
        for relative in (
            "portaineree/config.yaml",
            "portaineree/Dockerfile",
            "portaineree/CHANGELOG.md",
            "security/accepted-risks.yaml",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("updated\n")
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    first = run_update("first")
    assert first.returncode == 0, first.stderr
    branch = "automation/portainer-9.0.0"
    bot_sha = git(tmp_path, "--git-dir", str(remote), "rev-parse", branch)
    (tmp_path / "output").write_text("")
    repeated = run_update("repeated")
    assert repeated.returncode == 0, repeated.stderr
    assert git(tmp_path, "--git-dir", str(remote), "rev-parse", branch) == bot_sha
    assert "operation=\n" in (tmp_path / "output").read_text()

    review = tmp_path / "review"
    git(tmp_path, "clone", "--quiet", "--branch", branch, str(remote), str(review))
    (review / "security/accepted-risks.yaml").write_text("reviewed\n")
    git(review, "add", ".")
    git(
        review,
        "-c",
        "user.name=Reviewer",
        "-c",
        "user.email=reviewer@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "security: approve reviewed baseline",
    )
    git(review, "push", "--quiet", "origin", branch)
    reviewed_sha = git(review, "rev-parse", "HEAD")
    blocked = run_update("after-review")
    assert blocked.returncode != 0
    assert "contains manual commits" in blocked.stderr
    assert git(tmp_path, "--git-dir", str(remote), "rev-parse", branch) == reviewed_sha
