import json
from pathlib import Path

import pytest

from hass_portainer_ee_tools.cli import update_check_main
from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.update_check import (
    ReleaseCandidate,
    SecurityBridge,
    build_update_result,
    parse_release_records,
    parse_update_policy,
    select_update,
)
from hass_portainer_ee_tools.versions import Version

REPOSITORY_ROOT = Path(__file__).parents[2]
RELEASES_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/portainer-releases.json"
REGISTRY_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/registry.json"


def fixture_records() -> list[object]:
    return json.loads(RELEASES_FIXTURE.read_text(encoding="utf-8"))


def candidate(version: str, channel: str = "STS") -> ReleaseCandidate:
    return ReleaseCandidate(Version.parse(version), channel)


def bridge(
    *,
    affected: str = "2.44.0",
    target: str = "2.45.0",
) -> SecurityBridge:
    return SecurityBridge(
        advisory="GHSA-jxhm-qq8x-v4c6",
        affected_sts_through=Version.parse(affected),
        target_version=Version.parse(target),
        target_channel="LTS",
    )


def test_parse_release_records_filters_unpublished_and_nonstandard_names() -> None:
    releases = parse_release_records(fixture_records())

    assert releases == [
        candidate("2.43.5"),
        candidate("2.44.0"),
        candidate("2.44.1"),
        candidate("2.45.0", "LTS"),
    ]


def test_reject_release_name_and_tag_mismatch() -> None:
    records = fixture_records()
    records[2]["tag_name"] = "2.44.1-mismatch"  # type: ignore[index]

    with pytest.raises(PortainerToolError, match="release name and tag do not match"):
        parse_release_records(records)


def test_reject_duplicate_release_version() -> None:
    records = fixture_records()
    records.append(dict(records[2]))  # type: ignore[arg-type]

    with pytest.raises(PortainerToolError, match="duplicate release"):
        parse_release_records(records)


@pytest.mark.parametrize(
    "records",
    [
        {"message": "not a list"},
        [{"tag_name": "2.44.0"}],
        [
            {
                "tag_name": "2.44.0",
                "name": "Release 2.44.0 STS",
                "draft": 0,
                "prerelease": False,
            }
        ],
    ],
)
def test_reject_invalid_release_response(records: object) -> None:
    with pytest.raises(PortainerToolError, match="release response"):
        parse_release_records(records)


def test_security_bridge_has_priority() -> None:
    selected = select_update(
        Version.parse("2.44.0"),
        [candidate("2.44.1"), candidate("2.45.0", "LTS")],
        [bridge()],
    )

    assert selected == (candidate("2.45.0", "LTS"), "security_bridge")


def test_highest_newer_sts_is_selected_without_bridge() -> None:
    selected = select_update(
        Version.parse("2.43.5"),
        [candidate("2.44.0"), candidate("2.44.1"), candidate("2.45.0", "LTS")],
        [],
    )

    assert selected == (candidate("2.44.1"), "newer_sts")


def test_no_downgrade_or_equal_version() -> None:
    selected = select_update(
        Version.parse("2.45.0"),
        [candidate("2.44.1"), candidate("2.45.0", "LTS")],
        [bridge()],
    )

    assert selected is None


def test_highest_applicable_security_bridge_is_selected() -> None:
    selected = select_update(
        Version.parse("2.44.0"),
        [candidate("2.45.0", "LTS"), candidate("2.46.0", "LTS")],
        [bridge(target="2.45.0"), bridge(target="2.46.0")],
    )

    assert selected == (candidate("2.46.0", "LTS"), "security_bridge")


def test_parse_update_policy_requires_sts_and_nonempty_bridge_list() -> None:
    with pytest.raises(PortainerToolError, match="only STS"):
        parse_update_policy({"default_channel": "LTS", "security_bridges": [{}]})

    with pytest.raises(PortainerToolError, match="security bridge list"):
        parse_update_policy({"default_channel": "STS", "security_bridges": []})


def test_parse_update_policy_validates_bridge_fields() -> None:
    with pytest.raises(PortainerToolError, match="GitHub advisory"):
        parse_update_policy(
            {
                "default_channel": "STS",
                "security_bridges": [
                    {
                        "advisory": "CVE-2026-0001",
                        "affected_sts_through": "2.44.0",
                        "target_version": "2.45.0",
                        "target_channel": "LTS",
                    }
                ],
            }
        )


def test_build_update_result_resolves_both_digests() -> None:
    calls: list[str] = []

    def resolve(image: str) -> str:
        calls.append(image)
        return "sha256:" + ("a" if "portainer-ee" in image else "b") * 64

    result = build_update_result(candidate("2.44.1"), "newer_sts", resolve)

    assert calls == [
        "portainer/portainer-ee:2.44.1-alpine",
        "portainer/agent:2.44.1-alpine",
    ]
    assert result["app_version"] == "2.44.1.1"
    assert result["target_channel"] == "STS"


def test_build_update_result_rejects_invalid_digest() -> None:
    with pytest.raises(PortainerToolError, match="invalid manifest digest"):
        build_update_result(candidate("2.44.1"), "newer_sts", lambda _image: "latest")


def test_cli_uses_local_fixtures_and_writes_only_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("UPDATE_CHECK_TEST_MODE", "1")

    status = update_check_main(
        [
            "--current-version",
            "2.44.0",
            "--releases-file",
            str(RELEASES_FIXTURE),
            "--registry-stub",
            str(REGISTRY_FIXTURE),
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert status == 0
    assert captured.err == ""
    assert result["target_version"] == "2.45.0"
    assert result["target_channel"] == "LTS"
    assert result["reason"] == "security_bridge"


def test_cli_rejects_fixture_arguments_outside_test_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("UPDATE_CHECK_TEST_MODE", raising=False)

    status = update_check_main(
        [
            "--current-version",
            "2.44.0",
            "--releases-file",
            str(RELEASES_FIXTURE),
            "--registry-stub",
            str(REGISTRY_FIXTURE),
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert "test parameters are forbidden" in captured.err


def test_cli_rejects_missing_registry_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("UPDATE_CHECK_TEST_MODE", "1")

    status = update_check_main(
        [
            "--current-version",
            "2.44.0",
            "--releases-file",
            str(RELEASES_FIXTURE),
            "--registry-stub",
            str(registry),
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert "does not contain a manifest" in captured.err
