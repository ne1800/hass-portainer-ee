"""Validate risk documentation separately from approval of a release image."""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .errors import PortainerToolError
from .yaml_io import load_yaml


@dataclass(frozen=True)
class Baseline:
    source_image: str
    approved_on: date
    expires_on: date
    findings: frozenset[tuple[str, str]]


def _date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("invalid date")


def check_security_policy(
    root: Path, *, require_current: bool = False, today: date | None = None
) -> Baseline:
    """Structure tests allow a pending update; release gates require approval."""
    try:
        risks = load_yaml(root / "security/accepted-risks.yaml")
        ignored = load_yaml(root / ".trivyignore.yaml")
        release = load_yaml(root / "release.yaml")
        baseline = risks["temporary_vulnerability_baseline"]
        vulnerabilities = ignored["vulnerabilities"]
        documented = [
            r for r in risks["accepted_risks"] if r["kind"] == "vulnerability"
        ]
        findings = frozenset((r["id"], r["purl"]) for r in documented)
        ignored_findings = frozenset((v["id"], v["purls"][0]) for v in vulnerabilities)
        expires = _date(baseline["expires_on"])
        approved = _date(baseline["approved_on"])
        if (
            findings != ignored_findings
            or len(findings) != len(documented)
            or len(findings) != len(vulnerabilities)
            or type(baseline["finding_count"]) is not int
            or baseline["finding_count"] != len(findings)
            or approved >= expires
        ):
            raise ValueError("inconsistent vulnerability baseline")
        for vulnerability in vulnerabilities:
            if (
                vulnerability["paths"] != ["portainer"]
                or len(vulnerability["purls"]) != 1
                or not vulnerability["statement"].strip()
                or _date(vulnerability["expired_at"]) != expires
            ):
                raise ValueError("invalid scoped vulnerability exception")
        for risk in documented:
            if (
                risk["severity"] != "HIGH"
                or not risk["rationale"].strip()
                or _date(risk["expires_on"]) != expires
            ):
                raise ValueError("invalid documented vulnerability exception")
        for condition in (
            "private_network_only",
            "administrator_only",
            "trusted_git_sources_only",
            "trusted_images_only",
        ):
            if baseline["operating_conditions"][condition] is not True:
                raise ValueError("operating conditions must remain enabled")
        root_risks = [r for r in risks["accepted_risks"] if r["id"] == "AVD-DS-0002"]
        if (
            len(root_risks) != 1
            or root_risks[0]["affected_version"] != release["app"]["version"]
            or len(ignored["misconfigurations"]) != 1
            or ignored["misconfigurations"][0]["id"] != "AVD-DS-0002"
            or ignored["misconfigurations"][0]["paths"] != ["portaineree/Dockerfile"]
        ):
            raise ValueError("invalid Docker socket root exception")
        source = baseline["source_image"]
        if not isinstance(source, str) or not source.startswith(
            "local/hass-portainer-ee:"
        ):
            raise ValueError("invalid baseline source image")
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise PortainerToolError(f"invalid security policy: {error}") from error

    if require_current:
        expected = f"local/hass-portainer-ee:{release['app']['version']}"
        if source != expected:
            raise PortainerToolError(
                "security baseline needs review for the new app version"
            )
        current_date = today or date.today()
        if not approved <= current_date < expires:
            raise PortainerToolError("security baseline is not currently approved")
    return Baseline(source, approved, expires, findings)


def check_scan_report(root: Path, report: object, baseline: Baseline) -> None:
    try:
        release = load_yaml(root / "release.yaml")
        labels = report["Metadata"]["ImageConfig"]["config"]["Labels"]
        if (
            labels["io.hass.version"] != release["app"]["version"]
            or labels["io.hass.arch"] not in release["image"]["architectures"]
            or labels["org.opencontainers.image.source"]
            != "https://github.com/ne1800/hass-portainer-ee"
        ):
            raise ValueError("scan does not belong to this release image")
        observed = []
        for result in report["Results"]:
            if result.get("Vulnerabilities"):
                raise ValueError("unaccepted HIGH or CRITICAL vulnerabilities found")
            for item in result.get("ExperimentalModifiedFindings", []):
                if (
                    item["Type"] == "vulnerability"
                    and item["Status"] == "ignored"
                    and item["Source"] == ".trivyignore.yaml"
                ):
                    finding = item["Finding"]
                    if finding["Severity"] != "HIGH":
                        raise ValueError(
                            "only documented HIGH findings may be accepted"
                        )
                    observed.append(
                        (finding["VulnerabilityID"], finding["PkgIdentifier"]["PURL"])
                    )
        if (
            len(observed) != len(baseline.findings)
            or set(observed) != baseline.findings
        ):
            raise ValueError("new or missing findings require another security review")
    except (KeyError, TypeError, ValueError) as error:
        raise PortainerToolError(f"security scan rejected: {error}") from error


def security_check_main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the current release security approval"
    )
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    try:
        root = Path.cwd()
        baseline = check_security_policy(root, require_current=True)
        if arguments.report:
            report = json.loads(arguments.report.read_text(encoding="utf-8"))
            check_scan_report(root, report, baseline)
    except (PortainerToolError, OSError, json.JSONDecodeError) as error:
        print(f"Security check failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Security approval verified; {len(baseline.findings)} temporary HIGH findings."
    )
    return 0
