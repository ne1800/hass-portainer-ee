import re
from dataclasses import dataclass

from .errors import PortainerToolError

VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]{0,8})\."
    r"(0|[1-9][0-9]{0,8})\."
    r"(0|[1-9][0-9]{0,8})"
)


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str, *, label: str = "version") -> "Version":
        match = VERSION_PATTERN.fullmatch(value)
        if match is None:
            raise PortainerToolError(f"invalid {label}: {value}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
