import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.release import check_release

REPOSITORY_ROOT = Path(__file__).parents[2]


def copy_release_tree(destination: Path) -> Path:
    (destination / "portaineree").mkdir(parents=True)
    for relative_path in (
        Path("release.yaml"),
        Path("portaineree/config.yaml"),
        Path("portaineree/Dockerfile"),
        Path("portaineree/CHANGELOG.md"),
    ):
        shutil.copy2(REPOSITORY_ROOT / relative_path, destination / relative_path)
    return destination


def update_yaml(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    yaml = YAML()
    with path.open(encoding="utf-8") as stream:
        value = yaml.load(stream)
    mutate(value)
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(value, stream)


def test_accept_consistent_release(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)

    summary = check_release(root, release_tag="v2.44.0.1")

    assert summary.app_version == "2.44.0.1"
    assert summary.portainer_version == "2.44.0"


def test_reject_mismatched_app_version(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    update_yaml(
        root / "portaineree/config.yaml",
        lambda data: data.update(version="2.44.0.2"),
    )

    with pytest.raises(PortainerToolError, match="app versions do not match"):
        check_release(root)


def test_reject_moving_runtime_tag(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    update_yaml(
        root / "portaineree/config.yaml",
        lambda data: data.update(image="ghcr.io/ne1800/hass-portainer-ee:latest"),
    )

    with pytest.raises(PortainerToolError, match="runtime image does not match"):
        check_release(root)


def test_reject_wrong_architectures(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    update_yaml(
        root / "portaineree/config.yaml",
        lambda data: data.update(arch=["amd64"]),
    )

    with pytest.raises(PortainerToolError, match="app architectures do not match"):
        check_release(root)


def test_reject_invalid_release_digest(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)

    def mutate(data: dict[str, object]) -> None:
        data["portainer"]["digest"] = "sha256:not-a-digest"  # type: ignore[index]

    update_yaml(root / "release.yaml", mutate)

    with pytest.raises(PortainerToolError, match="invalid Portainer digest"):
        check_release(root)


def test_reject_wrong_docker_base(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    dockerfile = root / "portaineree/Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8").replace(
            "portainer-ee:2.44.0-alpine", "portainer-ee:2.44.1-alpine"
        ),
        encoding="utf-8",
    )

    with pytest.raises(PortainerToolError, match="Dockerfile base does not match"):
        check_release(root)


def test_reject_multiple_docker_bases(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    dockerfile = root / "portaineree/Dockerfile"
    dockerfile.write_text(
        f"FROM scratch\n{dockerfile.read_text(encoding='utf-8')}", encoding="utf-8"
    )

    with pytest.raises(PortainerToolError, match="exactly one FROM"):
        check_release(root)


def test_reject_missing_changelog_entry(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    changelog = root / "portaineree/CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8").replace("2.44.0.1", "2.44.0.9"),
        encoding="utf-8",
    )

    with pytest.raises(PortainerToolError, match="changelog does not contain"):
        check_release(root)


@pytest.mark.parametrize("release_tag", ["2.44.0.1", "v2.44.0", "v2.44.0.0"])
def test_reject_invalid_release_tag_shape(tmp_path: Path, release_tag: str) -> None:
    root = copy_release_tree(tmp_path)

    with pytest.raises(PortainerToolError, match="vX.Y.Z.R format"):
        check_release(root, release_tag=release_tag)


def test_reject_mismatched_release_tag(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)

    with pytest.raises(PortainerToolError, match="does not match the app version"):
        check_release(root, release_tag="v2.44.0.2")


def test_reject_missing_required_file(tmp_path: Path) -> None:
    root = copy_release_tree(tmp_path)
    (root / "release.yaml").unlink()

    with pytest.raises(PortainerToolError, match="file is missing: release.yaml"):
        check_release(root)
