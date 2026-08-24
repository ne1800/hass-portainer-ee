import pytest

from hass_portainer_ee_tools.errors import PortainerToolError
from hass_portainer_ee_tools.versions import Version


@pytest.mark.parametrize(
    ("value", "parts"),
    [
        ("0.0.0", (0, 0, 0)),
        ("2.44.0", (2, 44, 0)),
        ("123456789.1.9", (123456789, 1, 9)),
    ],
)
def test_parse_valid_version(value: str, parts: tuple[int, int, int]) -> None:
    version = Version.parse(value)

    assert (version.major, version.minor, version.patch) == parts
    assert str(version) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2.44",
        "2.44.0.1",
        "02.44.0",
        "2.-1.0",
        "2.44.x",
        "1234567890.1.1",
    ],
)
def test_reject_invalid_version(value: str) -> None:
    with pytest.raises(PortainerToolError, match="invalid fixture version"):
        Version.parse(value, label="fixture version")


def test_versions_compare_numerically() -> None:
    assert Version.parse("2.10.0") > Version.parse("2.9.0")
    assert Version.parse("2.44.1") > Version.parse("2.44.0")
    assert Version.parse("3.0.0") > Version.parse("2.999.999")
