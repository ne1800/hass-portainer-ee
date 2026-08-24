import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PortainerToolError
from .versions import Version
from .yaml_io import load_yaml

DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
RELEASE_TAG_PATTERN = re.compile(
    r"v(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"([1-9][0-9]*)"
)


@dataclass(frozen=True)
class ReleaseSummary:
    app_version: str
    portainer_version: str


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PortainerToolError(f"{label} must be a mapping")
    return value


def _string(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise PortainerToolError(f"{label} must be a string")
    return value


def check_release(root: Path, release_tag: str | None = None) -> ReleaseSummary:
    release_root = Path(root)
    paths = {
        "release": release_root / "release.yaml",
        "config": release_root / "portaineree/config.yaml",
        "dockerfile": release_root / "portaineree/Dockerfile",
        "changelog": release_root / "portaineree/CHANGELOG.md",
    }
    for path in paths.values():
        if not path.is_file():
            try:
                relative_path = path.relative_to(release_root)
            except ValueError:
                relative_path = path
            raise PortainerToolError(f"file is missing: {relative_path}")

    release = _mapping(load_yaml(paths["release"]), "release.yaml")
    config = _mapping(load_yaml(paths["config"]), "portaineree/config.yaml")

    schema = release.get("schema")
    if type(schema) is not int or schema != 1:
        raise PortainerToolError(f"unknown release.yaml schema: {schema}")

    app = _mapping(release.get("app"), "release.yaml app")
    image = _mapping(release.get("image"), "release.yaml image")
    portainer = _mapping(release.get("portainer"), "release.yaml portainer")
    agent = _mapping(release.get("agent"), "release.yaml agent")

    app_version = _string(app, "version", "app version")
    config_version = _string(config, "version", "config version")
    release_image = _string(image, "name", "release image")
    config_image = _string(config, "image", "runtime image")
    portainer_version = _string(portainer, "version", "Portainer version")
    portainer_image = _string(portainer, "image", "Portainer image")
    portainer_digest = _string(portainer, "digest", "Portainer digest")
    agent_image = _string(agent, "image", "agent image")
    agent_digest = _string(agent, "digest", "agent digest")

    if app_version != config_version:
        raise PortainerToolError("app versions do not match")
    Version.parse(portainer_version, label="Portainer version")
    wrapper_match = re.fullmatch(
        rf"{re.escape(portainer_version)}\.([1-9][0-9]*)", app_version
    )
    if wrapper_match is None:
        raise PortainerToolError(
            f"app version is not a wrapper revision of Portainer {portainer_version}"
        )

    if release_image != "ghcr.io/ne1800/hass-portainer-ee":
        raise PortainerToolError("unexpected release image name")
    if config_image != release_image:
        raise PortainerToolError("runtime image does not match release.yaml")
    if "{arch}" in config_image:
        raise PortainerToolError("runtime image must not use an {arch} placeholder")
    if re.search(r":(?:latest|lts|sts)$", config_image):
        raise PortainerToolError("moving runtime tag is prohibited")

    release_architectures = image.get("architectures")
    config_architectures = config.get("arch")
    expected_architectures = ["amd64", "aarch64"]
    if release_architectures != expected_architectures:
        raise PortainerToolError("release.yaml must contain exactly amd64 and aarch64")
    if config_architectures != release_architectures:
        raise PortainerToolError("app architectures do not match release.yaml")

    expected_portainer_image = f"portainer/portainer-ee:{portainer_version}-alpine"
    expected_agent_image = f"portainer/agent:{portainer_version}-alpine"
    if portainer_image != expected_portainer_image:
        raise PortainerToolError("Portainer image and version do not match")
    if agent_image != expected_agent_image:
        raise PortainerToolError("agent image and Portainer version do not match")
    if DIGEST_PATTERN.fullmatch(portainer_digest) is None:
        raise PortainerToolError("invalid Portainer digest")
    if DIGEST_PATTERN.fullmatch(agent_digest) is None:
        raise PortainerToolError("invalid agent digest")

    try:
        dockerfile = paths["dockerfile"].read_text(encoding="utf-8")
        changelog = paths["changelog"].read_text(encoding="utf-8")
    except OSError as error:
        raise PortainerToolError("release text file could not be read") from error

    from_references = []
    for line in dockerfile.splitlines():
        fields = line.split()
        if fields and fields[0] == "FROM":
            from_references.append(fields[1] if len(fields) > 1 else "")
    if len(from_references) != 1:
        raise PortainerToolError("Dockerfile must contain exactly one FROM")
    expected_from = f"{portainer_image}@{portainer_digest}"
    if from_references[0] != expected_from:
        raise PortainerToolError("Dockerfile base does not match release.yaml")

    if f"## [{app_version}]" not in changelog:
        raise PortainerToolError(
            f"changelog does not contain app version {app_version}"
        )

    if release_tag:
        if RELEASE_TAG_PATTERN.fullmatch(release_tag) is None:
            raise PortainerToolError("release tag does not use the vX.Y.Z.R format")
        if release_tag.removeprefix("v") != app_version:
            raise PortainerToolError("release tag does not match the app version")

    return ReleaseSummary(
        app_version=app_version,
        portainer_version=portainer_version,
    )
