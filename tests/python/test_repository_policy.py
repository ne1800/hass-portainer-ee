import json
import re
import tomllib
from pathlib import Path

from hass_portainer_ee_tools.yaml_io import load_yaml

ROOT = Path(__file__).parents[2]


def test_tools_have_explicit_versions_and_python_stays_supported() -> None:
    tools = tomllib.loads((ROOT / "mise.toml").read_text())["tools"]
    for name in (
        "gitleaks",
        "gh",
        "prek",
        "python",
        "uv",
        "aqua:docker/buildx",
        "actionlint",
        "cosign",
        "hadolint",
        "jq",
        "regctl",
        "trivy",
        "yq",
    ):
        assert re.fullmatch(r"\d+\.\d+(?:\.\d+)?", tools[name]), name
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    bounds = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)", project["requires-python"])
    assert bounds, (
        "Python support must declare its lower and upper minor-version bounds"
    )
    lower = tuple(map(int, bounds.group(1, 2)))
    upper = tuple(map(int, bounds.group(3, 4)))
    runtime = tuple(map(int, tools["python"].split(".")[:2]))
    assert lower <= runtime < upper

    renovate = json.loads((ROOT / "renovate.json").read_text())
    # Renovate normalizes Mise's depName=python to packageName=python/cpython.
    # PEP 621 uses packageName=python for requires-python.
    for manager, package_name in (("mise", "python/cpython"), ("pep621", "python")):
        rules = [
            r
            for r in renovate["packageRules"]
            if manager in r.get("matchManagers", [])
            and package_name in r.get("matchPackageNames", [])
        ]
        assert len(rules) == 1, (manager, package_name)
        assert rules[0]["allowedVersions"] == f"<{upper[0]}.{upper[1]}"
        assert "matchUpdateTypes" not in rules[0]

    hooks = load_yaml(ROOT / ".pre-commit-config.yaml")
    minimum = tuple(map(int, hooks["minimum_prek_version"].split(".")))
    selected = tuple(map(int, tools["prek"].split(".")))
    assert minimum <= selected
