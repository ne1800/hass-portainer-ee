import json
import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from hass_portainer_ee_tools.cli import update_apply_main
from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.release import check_release
from hass_portainer_ee_tools.update_apply import MANAGED_FILES, apply_update

REPOSITORY_ROOT = Path(__file__).parents[2]
SERVER_2441 = "sha256:" + "a" * 64
AGENT_2441 = "sha256:" + "b" * 64
SERVER_2450 = "sha256:" + "1" * 64
AGENT_2450 = "sha256:" + "2" * 64


def copy_update_tree(destination: Path) -> Path:
    for relative_path in (*MANAGED_FILES, Path("update-policy.yaml")):
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY_ROOT / relative_path, target)
    return destination


def update_document(
    *,
    version: str = "2.44.1",
    channel: str = "STS",
    reason: str = "newer_sts",
    server_digest: str = SERVER_2441,
    agent_digest: str = AGENT_2441,
) -> dict[str, bool | str]:
    return {
        "update_available": True,
        "target_version": version,
        "target_channel": channel,
        "reason": reason,
        "app_version": f"{version}.1",
        "server_digest": server_digest,
        "agent_digest": agent_digest,
        "release_url": (
            f"https://github.com/portainer/portainer/releases/tag/{version}"
        ),
    }


def write_update(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    return path


def load_yaml(path: Path) -> object:
    yaml = YAML(typ="safe")
    with path.open(encoding="utf-8") as stream:
        return yaml.load(stream)


def managed_bytes(root: Path) -> dict[Path, bytes]:
    return {relative: (root / relative).read_bytes() for relative in MANAGED_FILES}


def test_apply_newer_sts_update(tmp_path: Path) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(tmp_path / "update.json", update_document())

    result = apply_update(
        root,
        document,
        repository_root=REPOSITORY_ROOT,
        test_mode=True,
    )

    release = load_yaml(root / "release.yaml")
    risks = load_yaml(root / "security/accepted-risks.yaml")
    assert result.app_version == "2.44.1.1"
    assert release["portainer"]["version"] == "2.44.1"  # type: ignore[index]
    assert release["portainer"]["channel"] == "STS"  # type: ignore[index]
    root_risk = next(  # type: ignore[union-attr]
        item for item in risks["accepted_risks"] if item["id"] == "AVD-DS-0002"
    )
    assert root_risk["affected_version"] == "2.44.1.1"
    assert any(  # type: ignore[union-attr]
        item["id"] == "GHSA-jxhm-qq8x-v4c6" for item in risks["accepted_risks"]
    )
    assert "## [2.44.1.1]" in (root / "portaineree/CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    check_release(root)


def test_apply_configured_security_bridge(tmp_path: Path) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(
        tmp_path / "update.json",
        update_document(
            version="2.45.0",
            channel="LTS",
            reason="security_bridge",
            server_digest=SERVER_2450,
            agent_digest=AGENT_2450,
        ),
    )

    apply_update(
        root,
        document,
        repository_root=REPOSITORY_ROOT,
        test_mode=True,
    )

    risks = load_yaml(root / "security/accepted-risks.yaml")
    assert not any(  # type: ignore[union-attr]
        item["id"] == "GHSA-jxhm-qq8x-v4c6" for item in risks["accepted_risks"]
    )
    resolved = [  # type: ignore[index]
        item
        for item in risks["resolved_advisories"]  # type: ignore[index]
        if item["id"] == "GHSA-jxhm-qq8x-v4c6"
    ]
    assert resolved == [
        {
            "id": "GHSA-jxhm-qq8x-v4c6",
            "fixed_in": "2.45.0",
            "release_url": "https://github.com/portainer/portainer/releases/tag/2.45.0",
        }
    ]
    assert "FROM portainer/portainer-ee:2.45.0-alpine@" + SERVER_2450 in (
        root / "portaineree/Dockerfile"
    ).read_text(encoding="utf-8")
    check_release(root)


def test_forced_failure_restores_every_managed_file(tmp_path: Path) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(tmp_path / "update.json", update_document())
    before = managed_bytes(root)

    with pytest.raises(PortainerToolError, match="forced transaction failure"):
        apply_update(
            root,
            document,
            repository_root=REPOSITORY_ROOT,
            test_mode=True,
            fail_after_install=True,
        )

    assert managed_bytes(root) == before
    assert list(root.glob(".update-apply.*")) == []


def test_prepare_failure_cleans_transaction_without_target_changes(
    tmp_path: Path,
) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(tmp_path / "update.json", update_document())
    changelog = root / "portaineree/CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8") + "\n## [2.44.1.1]\n",
        encoding="utf-8",
    )
    before = managed_bytes(root)

    with pytest.raises(PortainerToolError, match="already contains"):
        apply_update(root, document, repository_root=REPOSITORY_ROOT, test_mode=True)

    assert managed_bytes(root) == before
    assert list(root.glob(".update-apply.*")) == []


def test_repeated_update_is_rejected_without_changes(tmp_path: Path) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(tmp_path / "update.json", update_document())
    apply_update(root, document, repository_root=REPOSITORY_ROOT, test_mode=True)
    before = managed_bytes(root)

    with pytest.raises(PortainerToolError, match="target version is not newer"):
        apply_update(root, document, repository_root=REPOSITORY_ROOT, test_mode=True)

    assert managed_bytes(root) == before


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(update_available=False),
        lambda value: value.update(extra="forbidden"),
        lambda value: value.pop("agent_digest"),
        lambda value: value.update(app_version="2.44.1.2"),
        lambda value: value.update(release_url="https://example.invalid/release"),
        lambda value: value.update(reason="security_bridge", target_channel="STS"),
    ],
)
def test_reject_invalid_update_document(
    tmp_path: Path,
    mutate: object,
) -> None:
    root = copy_update_tree(tmp_path / "target")
    value = update_document()
    mutate(value)  # type: ignore[operator]
    document = write_update(tmp_path / "update.json", value)
    before = managed_bytes(root)

    with pytest.raises(PortainerToolError):
        apply_update(root, document, repository_root=REPOSITORY_ROOT, test_mode=True)

    assert managed_bytes(root) == before


def test_reject_managed_symlink(tmp_path: Path) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(tmp_path / "update.json", update_document())
    config = root / "portaineree/config.yaml"
    real_config = root / "portaineree/config-real.yaml"
    config.rename(real_config)
    config.symlink_to(real_config)

    with pytest.raises(PortainerToolError, match="missing or is a symlink"):
        apply_update(root, document, repository_root=REPOSITORY_ROOT, test_mode=True)


def test_test_mode_rejects_repository_as_target(tmp_path: Path) -> None:
    document = write_update(tmp_path / "update.json", update_document())

    with pytest.raises(PortainerToolError, match="requires a separate"):
        apply_update(
            REPOSITORY_ROOT,
            document,
            repository_root=REPOSITORY_ROOT,
            test_mode=True,
        )


def test_cli_applies_fixture_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = copy_update_tree(tmp_path / "target")
    document = write_update(tmp_path / "update.json", update_document())
    monkeypatch.setenv("UPDATE_APPLY_TEST_MODE", "1")

    status = update_apply_main(["--root", str(root), str(document)])

    captured = capsys.readouterr()
    assert status == 0
    assert captured.err == ""
    assert "Prepared Portainer update: 2.44.1.1 (STS, newer_sts)." in captured.out


def test_cli_rejects_symlinked_update_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = copy_update_tree(tmp_path / "target")
    real_document = write_update(tmp_path / "real-update.json", update_document())
    document = tmp_path / "update.json"
    document.symlink_to(real_document)
    monkeypatch.setenv("UPDATE_APPLY_TEST_MODE", "1")

    status = update_apply_main(["--root", str(root), str(document)])

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert "update JSON is not a regular file" in captured.err
