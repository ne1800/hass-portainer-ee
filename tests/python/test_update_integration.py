"""A pending version update must still pass the complete deterministic suite."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.security import check_security_policy
from hass_portainer_ee_tools.update_apply import apply_update

ROOT = Path(__file__).parents[2]


def test_pending_update_passes_full_suite(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        )
        .stdout.decode()
        .split("\0")
    )
    for relative in filter(None, tracked):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "MISE_STATE_DIR": str(tmp_path / "mise-state"),
        "MISE_TRUSTED_CONFIG_PATHS": str(root),
        # Prevent recursive execution, while keeping all other tests enabled.
        "PYTEST_ADDOPTS": "--ignore=tests/python/test_update_integration.py",
    }
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            arguments, cwd=root, env=env, text=True, capture_output=True, check=False
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    run("git", "init", "--quiet", "--initial-branch=main")
    run("git", "config", "core.hooksPath", "/dev/null")
    run("git", "config", "commit.gpgsign", "false")
    run("git", "add", ".")
    run(
        "git",
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "test: initial snapshot",
    )
    update = tmp_path / "update.json"
    update.write_text(
        json.dumps(
            {
                "update_available": True,
                "target_version": "9.0.0",
                "target_channel": "STS",
                "reason": "newer_sts",
                "app_version": "9.0.0.1",
                "server_digest": "sha256:" + "a" * 64,
                "agent_digest": "sha256:" + "b" * 64,
                "release_url": "https://github.com/portainer/portainer/releases/tag/9.0.0",
            }
        )
    )
    apply_update(root, update, repository_root=ROOT, test_mode=True)
    check_security_policy(root)
    with pytest.raises(PortainerToolError, match="needs review"):
        check_security_policy(root, require_current=True)

    run("mise", "install")
    result = run("mise", "run", "test")
    assert "shell test(s) and all Python tests passed" in result.stdout
