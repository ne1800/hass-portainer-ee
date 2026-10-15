from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.security import check_scan_report, check_security_policy
from hass_portainer_ee_tools.yaml_io import dump_yaml, load_yaml


@pytest.fixture
def policy_root(tmp_path: Path) -> Path:
    # The real repository may contain a pending update whose image has not
    # received approval yet. Unit fixtures must not inherit that state.
    (tmp_path / "security").mkdir()
    dump_yaml(
        tmp_path / "release.yaml",
        {
            "app": {"version": "1.0.0.1"},
            "image": {"architectures": ["amd64", "aarch64"]},
        },
    )
    finding = {
        "id": "CVE-2099-1234",
        "kind": "vulnerability",
        "purl": "pkg:golang/example.invalid/test@v1.0.0",
        "severity": "HIGH",
        "expires_on": "2026-02-01",
        "rationale": "Synthetic test finding",
    }
    dump_yaml(
        tmp_path / "security/accepted-risks.yaml",
        {
            "temporary_vulnerability_baseline": {
                "approved_on": "2026-01-01",
                "expires_on": "2026-02-01",
                "source_image": "local/hass-portainer-ee:1.0.0.1",
                "finding_count": 1,
                "operating_conditions": {
                    key: True
                    for key in (
                        "private_network_only",
                        "administrator_only",
                        "trusted_git_sources_only",
                        "trusted_images_only",
                    )
                },
            },
            "accepted_risks": [
                {
                    "id": "AVD-DS-0002",
                    "kind": "misconfiguration",
                    "affected_version": "1.0.0.1",
                },
                finding,
            ],
        },
    )
    dump_yaml(
        tmp_path / ".trivyignore.yaml",
        {
            "vulnerabilities": [
                {
                    "id": finding["id"],
                    "purls": [finding["purl"]],
                    "paths": ["portainer"],
                    "expired_at": finding["expires_on"],
                    "statement": finding["rationale"],
                }
            ],
            "misconfigurations": [
                {"id": "AVD-DS-0002", "paths": ["portaineree/Dockerfile"]}
            ],
        },
    )
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
