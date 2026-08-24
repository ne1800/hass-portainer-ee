from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .errors import PortainerToolError


def load_yaml(path: Path, *, round_trip: bool = False) -> Any:
    yaml = YAML(typ="rt" if round_trip else "safe")
    if round_trip:
        yaml.preserve_quotes = True
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.load(stream)
    except (OSError, YAMLError) as error:
        raise PortainerToolError(f"could not read YAML file: {path}") from error


def dump_yaml(path: Path, value: Any) -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    try:
        with path.open("w", encoding="utf-8") as stream:
            yaml.dump(value, stream)
    except (OSError, YAMLError) as error:
        raise PortainerToolError(f"could not write YAML file: {path}") from error
