import json
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PortainerToolError
from .release import DIGEST_PATTERN
from .versions import Version

RELEASE_NAME_PATTERN = re.compile(
    r"Release "
    r"(?P<version>(?:0|[1-9][0-9]{0,8})\."
    r"(?:0|[1-9][0-9]{0,8})\."
    r"(?:0|[1-9][0-9]{0,8})) "
    r"(?P<channel>STS|LTS)"
)
ADVISORY_PATTERN = re.compile(r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}")


@dataclass(frozen=True, order=True)
class ReleaseCandidate:
    version: Version
    channel: str


@dataclass(frozen=True)
class SecurityBridge:
    advisory: str
    affected_sts_through: Version
    target_version: Version
    target_channel: str


def parse_release_records(records: object) -> list[ReleaseCandidate]:
    if not isinstance(records, list):
        raise PortainerToolError("release response is not an array")

    candidates: list[ReleaseCandidate] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise PortainerToolError("release response contains an invalid record")
        tag_name = record.get("tag_name")
        name = record.get("name")
        draft = record.get("draft")
        prerelease = record.get("prerelease")
        if (
            not isinstance(tag_name, str)
            or not isinstance(name, str)
            or type(draft) is not bool
            or type(prerelease) is not bool
        ):
            raise PortainerToolError("release response contains an invalid record")
        if draft or prerelease:
            continue

        match = RELEASE_NAME_PATTERN.fullmatch(name)
        if match is None:
            continue
        version_text = match.group("version")
        if tag_name != version_text:
            raise PortainerToolError("release name and tag do not match")
        candidates.append(
            ReleaseCandidate(
                version=Version.parse(version_text, label="release version"),
                channel=match.group("channel"),
            )
        )

    seen_versions: set[Version] = set()
    for candidate in candidates:
        if candidate.version in seen_versions:
            raise PortainerToolError("release response contains a duplicate release")
        seen_versions.add(candidate.version)
    return sorted(candidates)


def parse_update_policy(value: object) -> tuple[str, list[SecurityBridge]]:
    if not isinstance(value, Mapping):
        raise PortainerToolError("update-policy.yaml must contain a mapping")
    default_channel = value.get("default_channel")
    if default_channel != "STS":
        raise PortainerToolError("only STS is allowed as the default channel")
    bridge_values = value.get("security_bridges")
    if not isinstance(bridge_values, list) or not bridge_values:
        raise PortainerToolError(
            "update-policy.yaml does not contain a valid security bridge list"
        )

    bridges: list[SecurityBridge] = []
    for bridge_value in bridge_values:
        if not isinstance(bridge_value, Mapping):
            raise PortainerToolError("security bridge must be a mapping")
        advisory = bridge_value.get("advisory")
        affected = bridge_value.get("affected_sts_through")
        target = bridge_value.get("target_version")
        target_channel = bridge_value.get("target_channel")
        if (
            not isinstance(advisory, str)
            or ADVISORY_PATTERN.fullmatch(advisory) is None
        ):
            raise PortainerToolError(
                "security bridge does not contain a valid GitHub advisory"
            )
        if not isinstance(affected, str):
            raise PortainerToolError(
                "invalid affected STS version in update-policy.yaml"
            )
        if not isinstance(target, str):
            raise PortainerToolError("invalid bridge version in update-policy.yaml")
        if target_channel != "LTS":
            raise PortainerToolError("security bridge must target the LTS channel")
        bridges.append(
            SecurityBridge(
                advisory=advisory,
                affected_sts_through=Version.parse(
                    affected, label="affected STS version in update-policy.yaml"
                ),
                target_version=Version.parse(
                    target, label="bridge version in update-policy.yaml"
                ),
                target_channel=target_channel,
            )
        )
    return default_channel, bridges


def select_update(
    current: Version,
    releases: list[ReleaseCandidate],
    bridges: list[SecurityBridge],
) -> tuple[ReleaseCandidate, str] | None:
    released = {(item.version, item.channel): item for item in releases}
    applicable = [
        bridge
        for bridge in bridges
        if current <= bridge.affected_sts_through
        and bridge.target_version > current
        and (bridge.target_version, bridge.target_channel) in released
    ]
    if applicable:
        bridge = max(applicable, key=lambda item: item.target_version)
        return released[
            (bridge.target_version, bridge.target_channel)
        ], "security_bridge"

    sts_candidates = [
        item for item in releases if item.channel == "STS" and item.version > current
    ]
    if not sts_candidates:
        return None
    return max(sts_candidates, key=lambda item: item.version), "newer_sts"


def build_update_result(
    target: ReleaseCandidate,
    reason: str,
    resolve_digest: Callable[[str], str],
) -> dict[str, bool | str]:
    target_version = str(target.version)
    server_image = f"portainer/portainer-ee:{target_version}-alpine"
    agent_image = f"portainer/agent:{target_version}-alpine"
    server_digest = resolve_digest(server_image)
    agent_digest = resolve_digest(agent_image)
    for image, digest in (
        (server_image, server_digest),
        (agent_image, agent_digest),
    ):
        if DIGEST_PATTERN.fullmatch(digest) is None:
            raise PortainerToolError(f"invalid manifest digest for {image}")

    return {
        "update_available": True,
        "target_version": target_version,
        "target_channel": target.channel,
        "reason": reason,
        "app_version": f"{target_version}.1",
        "server_digest": server_digest,
        "agent_digest": agent_digest,
        "release_url": (
            f"https://github.com/portainer/portainer/releases/tag/{target_version}"
        ),
    }


def load_json_file(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PortainerToolError(f"{label} could not be read") from error


def load_official_releases() -> object:
    command = [
        "gh",
        "api",
        "--method",
        "GET",
        "--header",
        "Accept: application/vnd.github+json",
        "--header",
        "X-GitHub-Api-Version: 2022-11-28",
        "--field",
        "per_page=100",
        "repos/portainer/portainer/releases",
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as error:
        raise PortainerToolError(
            "official Portainer releases could not be loaded"
        ) from error
    if result.returncode != 0:
        raise PortainerToolError("official Portainer releases could not be loaded")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise PortainerToolError(
            "official Portainer releases returned invalid JSON"
        ) from error


def registry_digest(image: str) -> str:
    try:
        result = subprocess.run(
            ["regctl", "image", "digest", image],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise PortainerToolError(
            f"manifest digest could not be resolved: {image}"
        ) from error
    if result.returncode != 0:
        raise PortainerToolError(f"manifest digest could not be resolved: {image}")
    return result.stdout.strip()


def stub_digest_resolver(value: object) -> Callable[[str], str]:
    if not isinstance(value, Mapping):
        raise PortainerToolError("registry stub must contain a JSON object")

    def resolve(image: str) -> str:
        digest = value.get(image)
        if not isinstance(digest, str):
            raise PortainerToolError(
                f"registry stub does not contain a manifest for {image}"
            )
        return digest

    return resolve
