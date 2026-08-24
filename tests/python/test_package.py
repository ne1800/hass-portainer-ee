from hass_portainer_ee_tools.errors import PortainerToolError


def test_expected_tool_error_is_importable() -> None:
    error = PortainerToolError("fixture")

    assert str(error) == "fixture"
