import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .errors import PortainerToolError
from .release import check_release
from .update_apply import apply_update
from .update_check import (
    build_update_result,
    load_json_file,
    load_official_releases,
    parse_release_records,
    parse_update_policy,
    registry_digest,
    select_update,
    stub_digest_resolver,
)
from .versions import Version
from .yaml_io import load_yaml


def release_check_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="release:check",
        description="Verify release metadata and immutable image pins.",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--release-tag")
    arguments = parser.parse_args(argv)

    try:
        summary = check_release(arguments.root, release_tag=arguments.release_tag)
    except PortainerToolError as error:
        print(f"Release check failed: {error}", file=sys.stderr)
        return 1

    print(
        "Release metadata is consistent: "
        f"app {summary.app_version}, Portainer {summary.portainer_version}, "
        "amd64+aarch64."
    )
    return 0


def _repository_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise PortainerToolError("repository root could not be resolved") from error
    if result.returncode != 0 or not result.stdout.strip():
        raise PortainerToolError("repository root could not be resolved")
    return Path(result.stdout.strip())


def update_check_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="update:check",
        description="Check official Portainer releases for allowed updates.",
    )
    parser.add_argument("--current-version")
    parser.add_argument("--releases-file", type=Path)
    parser.add_argument("--registry-stub", type=Path)
    arguments = parser.parse_args(argv)

    try:
        test_mode = os.environ.get("UPDATE_CHECK_TEST_MODE", "0") == "1"
        fixture_values = (
            arguments.current_version,
            arguments.releases_file,
            arguments.registry_stub,
        )
        if not test_mode and any(value is not None for value in fixture_values):
            raise PortainerToolError(
                "test parameters are forbidden outside UPDATE_CHECK_TEST_MODE=1"
            )
        if test_mode and any(value is None for value in fixture_values):
            raise PortainerToolError(
                "test mode requires a version, release fixture, and registry stub"
            )

        repository_root = _repository_root()
        policy_value = load_yaml(repository_root / "update-policy.yaml")
        _, bridges = parse_update_policy(policy_value)

        if test_mode:
            current = Version.parse(arguments.current_version, label="current version")
            release_values = load_json_file(arguments.releases_file, "release file")
            registry_values = load_json_file(arguments.registry_stub, "registry stub")
            resolve_digest = stub_digest_resolver(registry_values)
        else:
            release_metadata = load_yaml(repository_root / "release.yaml")
            try:
                current_value = release_metadata["portainer"]["version"]
            except (KeyError, TypeError) as error:
                raise PortainerToolError(
                    "Portainer version could not be read"
                ) from error
            if not isinstance(current_value, str):
                raise PortainerToolError("Portainer version could not be read")
            current = Version.parse(current_value, label="current version")
            release_values = load_official_releases()
            resolve_digest = registry_digest

        releases = parse_release_records(release_values)
        selection = select_update(current, releases, bridges)
        if selection is None:
            payload: dict[str, bool | str] = {
                "update_available": False,
                "current_version": str(current),
            }
        else:
            target, reason = selection
            payload = build_update_result(target, reason, resolve_digest)
    except PortainerToolError as error:
        print(f"Portainer update check failed: {error}", file=sys.stderr)
        return 1

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def update_apply_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="update:apply",
        description="Apply validated Portainer update output reproducibly.",
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("update_file", type=Path)
    arguments = parser.parse_args(argv)

    try:
        repository_root = _repository_root()
        target_root = arguments.root or repository_root
        update_file = arguments.update_file
        if not update_file.is_absolute():
            update_file = Path.cwd() / update_file
        document = apply_update(
            target_root,
            update_file,
            repository_root=repository_root,
            test_mode=os.environ.get("UPDATE_APPLY_TEST_MODE", "0") == "1",
            fail_after_install=(
                os.environ.get("UPDATE_APPLY_TEST_FAIL_AFTER_INSTALL", "0") == "1"
            ),
        )
    except PortainerToolError as error:
        print(f"Portainer update application failed: {error}", file=sys.stderr)
        return 1

    print(
        f"Prepared Portainer update: {document.app_version} "
        f"({document.target_channel}, {document.reason})."
    )
    return 0
