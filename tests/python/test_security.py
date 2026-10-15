import shutil
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.security import check_scan_report, check_security_policy
from hass_portainer_ee_tools.yaml_io import dump_yaml, load_yaml

ROOT = Path(__file__).parents[2]


@pytest.fixture
def policy_root(tmp_path: Path) -> Path:
    for relative in (
        "release.yaml",
        "security/accepted-risks.yaml",
        ".trivyignore.yaml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return tmp_path


def scan_report(root: Path) -> dict:
    baseline = check_security_policy(root)
    release = load_yaml(root / "release.yaml")
    return {
        "Metadata": {
            "ImageConfig": {
                "config": {
                    "Labels": {
                        "io.hass.version": release["app"]["version"],
                        "io.hass.arch": "amd64",
                        "org.opencontainers.image.source": "https://github.com/ne1800/hass-portainer-ee",
                    }
                }
            }
        },
        "Results": [
            {
                "ExperimentalModifiedFindings": [
                    {
                        "Type": "vulnerability",
                        "Status": "ignored",
                        "Source": ".trivyignore.yaml",
                        "Finding": {
                            "VulnerabilityID": identifier,
                            "PkgIdentifier": {"PURL": purl},
                            "Severity": "HIGH",
                        },
                    }
                    for identifier, purl in sorted(baseline.findings)
                ]
            }
        ],
    }


def test_current_policy_matches_both_report_architectures(policy_root: Path) -> None:
    baseline = check_security_policy(policy_root)
    check_security_policy(policy_root, require_current=True, today=baseline.approved_on)
    report = scan_report(policy_root)
    for arch in ("amd64", "aarch64"):
        report["Metadata"]["ImageConfig"]["config"]["Labels"]["io.hass.arch"] = arch
        check_scan_report(policy_root, report, baseline)


def test_pending_update_does_not_inherit_approval(policy_root: Path) -> None:
    release = load_yaml(policy_root / "release.yaml")
    release["app"]["version"] = "9.0.0.1"
    dump_yaml(policy_root / "release.yaml", release)
    risks = load_yaml(policy_root / "security/accepted-risks.yaml")
    next(r for r in risks["accepted_risks"] if r["id"] == "AVD-DS-0002")[
        "affected_version"
    ] = "9.0.0.1"
    dump_yaml(policy_root / "security/accepted-risks.yaml", risks)

    check_security_policy(policy_root)
    with pytest.raises(PortainerToolError, match="needs review"):
        check_security_policy(policy_root, require_current=True)


@pytest.mark.parametrize("when", [date(2000, 1, 1), date(2100, 1, 1)])
def test_expired_or_future_approval_is_rejected(policy_root: Path, when: date) -> None:
    with pytest.raises(PortainerToolError, match="not currently approved"):
        check_security_policy(policy_root, require_current=True, today=when)


def test_expiration_date_is_exclusive(policy_root: Path) -> None:
    baseline = check_security_policy(policy_root)
    with pytest.raises(PortainerToolError, match="not currently approved"):
        check_security_policy(
            policy_root, require_current=True, today=baseline.expires_on
        )


@pytest.mark.parametrize(
    "change", ["new", "missing", "critical", "wrong_image", "empty"]
)
def test_changed_scan_blocks_release(policy_root: Path, change: str) -> None:
    baseline = check_security_policy(policy_root)
    report = scan_report(policy_root)
    result = report["Results"][0]
    if change == "new":
        result["Vulnerabilities"] = [{"VulnerabilityID": "CVE-2099-0001"}]
    elif change == "missing":
        result["ExperimentalModifiedFindings"].pop()
    elif change == "critical":
        result["ExperimentalModifiedFindings"][0]["Finding"]["Severity"] = "CRITICAL"
    elif change == "wrong_image":
        report["Metadata"]["ImageConfig"]["config"]["Labels"]["io.hass.version"] = (
            "0.0.0.1"
        )
    else:
        report = {}

    with pytest.raises(PortainerToolError, match="security scan rejected"):
        check_scan_report(policy_root, report, baseline)


def test_desynchronized_risk_documentation_is_rejected(policy_root: Path) -> None:
    risks = load_yaml(policy_root / "security/accepted-risks.yaml")
    duplicate = deepcopy(
        next(r for r in risks["accepted_risks"] if r["kind"] == "vulnerability")
    )
    risks["accepted_risks"].append(duplicate)
    dump_yaml(policy_root / "security/accepted-risks.yaml", risks)
    with pytest.raises(PortainerToolError, match="inconsistent vulnerability baseline"):
        check_security_policy(policy_root)
