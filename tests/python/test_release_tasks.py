import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hass_portainer_ee_tools.yaml_io import load_yaml

ROOT = Path(__file__).parents[2]


def stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!{sys.executable}\nimport json, os, sys\n{body}\n")
    path.chmod(0o755)


@pytest.mark.parametrize(
    "failure", ["none", "signature", "metadata", "scan", "registry"]
)
def test_manifest_is_written_only_after_both_images_pass(
    tmp_path: Path, failure: str
) -> None:
    version = load_yaml(ROOT / "release.yaml")["app"]["version"]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    stub(
        tmp_path,
        "regctl",
        """
if sys.argv[1:3] == ['manifest', 'head']:
    status = '[http 403]' if os.environ['FAILURE'] == 'registry' else '[http 404]'
    print(status, file=sys.stderr)
    sys.exit(1)
arm = 'aarch64-' in sys.argv[3]
if sys.argv[1:3] == ['image', 'digest']:
    print('sha256:' + ('b' if arm else 'a') * 64)
elif sys.argv[1:3] == ['image', 'config']:
    revision = os.environ['COMMIT']
    if os.environ['FAILURE'] == 'metadata':
        revision = '0' * 40
    labels = {
        'io.hass.arch': 'aarch64' if arm else 'amd64',
        'io.hass.version': os.environ['VERSION'],
        'org.opencontainers.image.revision': revision,
        'org.opencontainers.image.source': 'https://github.com/ne1800/hass-portainer-ee',
    }
    print(json.dumps({
        'architecture': 'arm64' if arm else 'amd64',
        'os': 'linux', 'config': {'Labels': labels},
    }))
else:
    sys.exit(1)
""",
    )
    stub(
        tmp_path,
        "cosign",
        "if sys.argv[1] == 'verify' and os.environ['FAILURE'] == 'signature':\n"
        "    sys.exit(1)",
    )
    stub(
        tmp_path,
        "mise",
        "if 'security:scan' in sys.argv and 'aarch64-' in sys.argv[-1]:\n"
        "    sys.exit(1 if os.environ['FAILURE'] == 'scan' else 0)",
    )
    stub(
        tmp_path,
        "docker-cli-plugin-docker-buildx",
        "open(os.environ['PUBLISHED'], 'w').write(json.dumps(sys.argv[1:]))",
    )
    published = tmp_path / "published"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_REF_NAME": f"v{version}",
        "COMMIT": commit,
        "VERSION": version,
        "FAILURE": failure,
        "PUBLISHED": str(published),
    }

    result = subprocess.run(
        ["bash", str(ROOT / ".mise/tasks/release/manifest.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert (result.returncode == 0) == (failure == "none"), result.stderr
    assert published.exists() == (failure == "none")
    if published.exists():
        arguments = json.loads(published.read_text())
        assert "index:org.opencontainers.image.description=" in " ".join(arguments)
        sources = [arg for arg in arguments if "@sha256:" in arg]
        assert len(sources) == 2
        assert any("amd64-" in arg for arg in sources)
        assert any("aarch64-" in arg for arg in sources)


def test_missing_local_image_blocks_security_scan(tmp_path: Path) -> None:
    stub(tmp_path, "mise", "sys.exit(0)")
    stub(tmp_path, "docker", "sys.exit(1)")
    stub(
        tmp_path,
        "trivy",
        "assert sys.argv[1] == 'config', 'must not scan an absent local image'",
    )
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}

    result = subprocess.run(
        ["bash", str(ROOT / ".mise/tasks/security/scan.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Required local release image is missing" in result.stderr


def test_test_task_isolates_hook_environment(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    subprocess.run(["git", "init", "--quiet", str(fixture)], check=True)
    tests = fixture / "tests"
    tests.mkdir()
    probe = tests / "probe.sh"
    probe.write_text(
        "#!/bin/sh\nset -eu\n"
        'test -z "${GIT_DIR+x}"\n'
        'test -z "${GIT_WORK_TREE+x}"\n'
        'test -z "${GIT_CONFIG_COUNT+x}"\n'
        'test -z "${GIT_CONFIG_PARAMETERS+x}"\n'
        'test "$(git rev-parse --is-bare-repository)" = false\n'
    )
    probe.chmod(0o755)
    stub(tmp_path, "uv", "sys.exit(0)")
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "GIT_DIR": str(fixture / ".git"),
        "GIT_WORK_TREE": str(fixture),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": str(tmp_path / "hook"),
        "GIT_CONFIG_PARAMETERS": "'core.hooksPath=unused-hook'",
    }
    result = subprocess.run(
        ["bash", str(ROOT / ".mise/tasks/test.sh")],
        cwd=fixture,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "1 shell test(s)" in result.stdout
