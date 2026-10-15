import json
import os
import subprocess
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
