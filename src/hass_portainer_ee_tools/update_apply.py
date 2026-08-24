import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PortainerToolError
from .release import DIGEST_PATTERN, check_release
from .update_check import SecurityBridge, parse_update_policy
from .versions import Version
from .yaml_io import dump_yaml, load_yaml

MANAGED_FILES = (
    Path("release.yaml"),
    Path("portaineree/config.yaml"),
    Path("portaineree/Dockerfile"),
    Path("portaineree/CHANGELOG.md"),
    Path("security/accepted-risks.yaml"),
)
EXPECTED_UPDATE_KEYS = {
    "agent_digest",
    "app_version",
    "reason",
    "release_url",
    "server_digest",
    "target_channel",
    "target_version",
    "update_available",
}


@dataclass(frozen=True)
class UpdateDocument:
    target_version: Version
    target_channel: str
    reason: str
    app_version: str
    server_digest: str
    agent_digest: str
    release_url: str

    @classmethod
    def from_mapping(cls, value: object) -> "UpdateDocument":
        if not isinstance(value, Mapping) or set(value) != EXPECTED_UPDATE_KEYS:
            raise PortainerToolError("update JSON does not match the allowed schema")
        if value.get("update_available") is not True:
            raise PortainerToolError("update JSON does not match the allowed schema")
        string_keys = EXPECTED_UPDATE_KEYS - {"update_available"}
        if any(not isinstance(value.get(key), str) for key in string_keys):
            raise PortainerToolError("update JSON does not match the allowed schema")

        target_text = value["target_version"]
        target_version = Version.parse(target_text, label="target version")
        app_version = value["app_version"]
        if app_version != f"{target_version}.1":
            raise PortainerToolError(
                "app version is not the first wrapper revision of the target version"
            )

        server_digest = value["server_digest"]
        agent_digest = value["agent_digest"]
        if DIGEST_PATTERN.fullmatch(server_digest) is None:
            raise PortainerToolError("invalid server digest")
        if DIGEST_PATTERN.fullmatch(agent_digest) is None:
            raise PortainerToolError("invalid agent digest")

        release_url = value["release_url"]
        expected_url = (
            f"https://github.com/portainer/portainer/releases/tag/{target_version}"
        )
        if release_url != expected_url:
            raise PortainerToolError("unexpected release URL")

        reason = value["reason"]
        target_channel = value["target_channel"]
        if (reason, target_channel) not in {
            ("newer_sts", "STS"),
            ("security_bridge", "LTS"),
        }:
            raise PortainerToolError(
                "selection reason and target channel are not allowed"
            )

        return cls(
            target_version=target_version,
            target_channel=target_channel,
            reason=reason,
            app_version=app_version,
            server_digest=server_digest,
            agent_digest=agent_digest,
            release_url=release_url,
        )


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _load_update_document(path: Path) -> UpdateDocument:
    if not _is_regular_file(path):
        raise PortainerToolError("update JSON is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PortainerToolError(
            "update JSON does not match the allowed schema"
        ) from error
    return UpdateDocument.from_mapping(value)


def _resolve_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise PortainerToolError(f"{label} is missing: {path}") from error
    if not resolved.is_dir():
        raise PortainerToolError(f"{label} is missing: {path}")
    return resolved


def _validate_managed_files(root: Path) -> None:
    for relative_path in MANAGED_FILES:
        if not _is_regular_file(root / relative_path):
            raise PortainerToolError(
                f"managed file is missing or is a symlink: {relative_path}"
            )
    if not _is_regular_file(root / "update-policy.yaml"):
        raise PortainerToolError("update-policy.yaml is missing or is a symlink")


def _require_clean_managed_files(repository_root: Path) -> None:
    paths = [str(path) for path in (*MANAGED_FILES, Path("update-policy.yaml"))]
    for cached, message in (
        (False, "managed files contain unstaged changes"),
        (True, "managed files contain staged changes"),
    ):
        command = ["git", "-C", str(repository_root), "diff"]
        if cached:
            command.append("--cached")
        command.extend(["--quiet", "--", *paths])
        try:
            result = subprocess.run(command, check=False)
        except OSError as error:
            raise PortainerToolError(
                "managed file state could not be checked"
            ) from error
        if result.returncode == 1:
            raise PortainerToolError(message)
        if result.returncode != 0:
            raise PortainerToolError("managed file state could not be checked")


def _mutable_mapping(value: Any, label: str) -> MutableMapping[str, Any]:
    if not isinstance(value, MutableMapping):
        raise PortainerToolError(f"{label} must be a mapping")
    return value


def _select_bridge(
    document: UpdateDocument,
    bridges: list[SecurityBridge],
    current_version: Version,
) -> SecurityBridge | None:
    if document.reason != "security_bridge":
        if document.target_channel != "STS":
            raise PortainerToolError("regular update differs from the default channel")
        return None

    matches = [
        bridge
        for bridge in bridges
        if bridge.target_version == document.target_version
        and bridge.target_channel == document.target_channel
    ]
    if len(matches) != 1:
        raise PortainerToolError("target is not a unique configured security bridge")
    bridge = matches[0]
    if current_version > bridge.affected_sts_through:
        raise PortainerToolError(
            "current version is outside the configured security bridge"
        )
    return bridge


def _copy_managed_files(source: Path, destination: Path) -> None:
    for relative_path in MANAGED_FILES:
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative_path, target)


def _update_release_yaml(stage_root: Path, document: UpdateDocument) -> None:
    path = stage_root / "release.yaml"
    release = _mutable_mapping(load_yaml(path, round_trip=True), "release.yaml")
    app = _mutable_mapping(release.get("app"), "release.yaml app")
    portainer = _mutable_mapping(release.get("portainer"), "release.yaml portainer")
    agent = _mutable_mapping(release.get("agent"), "release.yaml agent")
    target_version = str(document.target_version)

    app["version"] = document.app_version
    portainer["channel"] = document.target_channel
    portainer["version"] = target_version
    portainer["image"] = f"portainer/portainer-ee:{target_version}-alpine"
    portainer["digest"] = document.server_digest
    agent["image"] = f"portainer/agent:{target_version}-alpine"
    agent["digest"] = document.agent_digest
    dump_yaml(path, release)


def _update_config_yaml(stage_root: Path, document: UpdateDocument) -> None:
    path = stage_root / "portaineree/config.yaml"
    config = _mutable_mapping(
        load_yaml(path, round_trip=True), "portaineree/config.yaml"
    )
    config["version"] = document.app_version
    dump_yaml(path, config)


def _update_accepted_risks(
    stage_root: Path,
    document: UpdateDocument,
    bridge: SecurityBridge | None,
) -> None:
    path = stage_root / "security/accepted-risks.yaml"
    risk_document = _mutable_mapping(
        load_yaml(path, round_trip=True), "security/accepted-risks.yaml"
    )
    accepted_risks = risk_document.get("accepted_risks")
    if not isinstance(accepted_risks, list):
        raise PortainerToolError("accepted_risks must be a list")

    root_exceptions = [
        item
        for item in accepted_risks
        if isinstance(item, MutableMapping) and item.get("id") == "AVD-DS-0002"
    ]
    if len(root_exceptions) != 1:
        raise PortainerToolError(
            "exactly one documented Docker root exception is expected"
        )
    root_exceptions[0]["affected_version"] = document.app_version

    if bridge is not None:
        advisory_exceptions = [
            item
            for item in accepted_risks
            if isinstance(item, Mapping) and item.get("id") == bridge.advisory
        ]
        if len(advisory_exceptions) != 1:
            raise PortainerToolError(
                "security bridge expects exactly one open advisory exception"
            )
        accepted_risks[:] = [
            item
            for item in accepted_risks
            if not isinstance(item, Mapping) or item.get("id") != bridge.advisory
        ]

        resolved = risk_document.get("resolved_advisories", [])
        if not isinstance(resolved, list):
            raise PortainerToolError("resolved_advisories must be a list")
        resolved = [
            item
            for item in resolved
            if not isinstance(item, Mapping) or item.get("id") != bridge.advisory
        ]
        resolved.append(
            {
                "id": bridge.advisory,
                "fixed_in": str(document.target_version),
                "release_url": document.release_url,
            }
        )
        risk_document["resolved_advisories"] = sorted(
            resolved,
            key=lambda item: (
                str(item.get("id", "")) if isinstance(item, Mapping) else ""
            ),
        )

    dump_yaml(path, risk_document)


def _update_dockerfile(stage_root: Path, document: UpdateDocument) -> None:
    path = stage_root / "portaineree/Dockerfile"
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as error:
        raise PortainerToolError("Dockerfile could not be read") from error
    from_indexes = [
        index
        for index, line in enumerate(lines)
        if line.split() and line.split()[0] == "FROM"
    ]
    if len(from_indexes) != 1:
        raise PortainerToolError("Dockerfile must contain exactly one FROM")
    target_version = str(document.target_version)
    reference = (
        f"portainer/portainer-ee:{target_version}-alpine@{document.server_digest}"
    )
    index = from_indexes[0]
    newline = "\n" if lines[index].endswith("\n") else ""
    lines[index] = f"FROM {reference}{newline}"
    try:
        path.write_text("".join(lines), encoding="utf-8")
    except OSError as error:
        raise PortainerToolError("Dockerfile could not be updated") from error


def _update_changelog(
    stage_root: Path,
    document: UpdateDocument,
    bridge: SecurityBridge | None,
) -> None:
    path = stage_root / "portaineree/CHANGELOG.md"
    try:
        changelog = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PortainerToolError("changelog could not be read") from error
    if f"## [{document.app_version}]" in changelog:
        raise PortainerToolError("changelog already contains the target version")
    heading = re_search_changelog_heading(changelog)
    if heading is None:
        raise PortainerToolError("changelog could not be extended")

    if bridge is None:
        change_reason = "Adopted a newer allowed STS version."
    else:
        change_reason = (
            f"Applied the configured LTS security bridge for {bridge.advisory}."
        )
    block = (
        f"## [{document.app_version}]\n\n"
        "### Changed\n\n"
        "- Updated Portainer Business Edition to "
        f"{document.target_version} ({document.target_channel}).\n"
        f"- {change_reason}\n"
        "- Pinned server and agent images immutably by manifest digest.\n"
        f"- Official release: {document.release_url}\n\n"
    )
    try:
        path.write_text(
            changelog[:heading] + block + changelog[heading:], encoding="utf-8"
        )
    except OSError as error:
        raise PortainerToolError("changelog could not be extended") from error


def re_search_changelog_heading(changelog: str) -> int | None:
    for line in changelog.splitlines(keepends=True):
        if line.startswith("## ["):
            return changelog.index(line)
    return None


def _prepare_stage(
    stage_root: Path,
    document: UpdateDocument,
    bridge: SecurityBridge | None,
) -> None:
    _update_release_yaml(stage_root, document)
    _update_config_yaml(stage_root, document)
    _update_accepted_risks(stage_root, document, bridge)
    _update_dockerfile(stage_root, document)
    _update_changelog(stage_root, document, bridge)
    try:
        check_release(stage_root)
    except PortainerToolError as error:
        raise PortainerToolError("prepared files are not release-consistent") from error


def _rollback(backup_root: Path, target_root: Path) -> None:
    try:
        for relative_path in MANAGED_FILES:
            shutil.copy2(backup_root / relative_path, target_root / relative_path)
    except OSError as error:
        raise PortainerToolError("update rollback failed") from error


def apply_update(
    target_root: Path,
    update_file: Path,
    *,
    repository_root: Path,
    test_mode: bool,
    fail_after_install: bool = False,
) -> UpdateDocument:
    repository_root = _resolve_directory(repository_root, "repository root")
    target_root = _resolve_directory(target_root, "target directory")
    if test_mode:
        if target_root == repository_root:
            raise PortainerToolError("test mode requires a separate --root directory")
    elif target_root != repository_root:
        raise PortainerToolError("--root is forbidden outside UPDATE_APPLY_TEST_MODE=1")

    _validate_managed_files(target_root)
    if not test_mode:
        _require_clean_managed_files(repository_root)
    document = _load_update_document(update_file)

    summary = check_release(target_root)
    current_version = Version.parse(
        summary.portainer_version, label="current Portainer version"
    )
    if document.target_version <= current_version:
        raise PortainerToolError(f"target version is not newer than {current_version}")
    _, bridges = parse_update_policy(load_yaml(target_root / "update-policy.yaml"))
    bridge = _select_bridge(document, bridges, current_version)

    try:
        transaction_root = Path(
            tempfile.mkdtemp(prefix=".update-apply.", dir=target_root)
        )
    except OSError as error:
        raise PortainerToolError("update transaction could not be prepared") from error
    stage_root = transaction_root / "stage"
    backup_root = transaction_root / "backup"
    install_started = False
    try:
        _copy_managed_files(target_root, stage_root)
        _copy_managed_files(target_root, backup_root)
        _prepare_stage(stage_root, document, bridge)
        install_started = True
        for relative_path in MANAGED_FILES:
            os.replace(stage_root / relative_path, target_root / relative_path)
        if fail_after_install:
            raise PortainerToolError("forced transaction failure in test mode")
        check_release(target_root)
    except Exception as error:
        if install_started:
            _rollback(backup_root, target_root)
        if isinstance(error, PortainerToolError):
            raise
        if install_started:
            raise PortainerToolError("update transaction failed") from error
        raise PortainerToolError("update transaction could not be prepared") from error
    finally:
        shutil.rmtree(transaction_root, ignore_errors=True)

    return document
