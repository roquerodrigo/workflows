from __future__ import annotations

import re
from dataclasses import dataclass

HEADER = re.compile(r"^(?P<type>[\w-]+)(?:\([^)]*\))?(?P<bang>!)?: ")
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
RELEASE_PLEASE_DEFAULT_VISIBLE_TYPES = frozenset({"feat", "fix", "perf", "revert"})


@dataclass(frozen=True)
class ConventionalCommit:
    type: str
    is_breaking: bool

    @classmethod
    def parse(cls, message: str) -> ConventionalCommit | None:
        match = HEADER.match(message)
        if match is None:
            return None
        is_breaking = match["bang"] is not None or BREAKING_FOOTER.search(message) is not None
        return cls(type=match["type"], is_breaking=is_breaking)


def visible_types(package_configuration: dict, root_configuration: dict) -> frozenset[str]:
    sections = package_configuration.get("changelog-sections") or root_configuration.get("changelog-sections")
    if not sections:
        return RELEASE_PLEASE_DEFAULT_VISIBLE_TYPES
    return frozenset(section["type"] for section in sections if not section.get("hidden"))
