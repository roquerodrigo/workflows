from __future__ import annotations

import re

NEXT_VERSION_HEADING = re.compile(r"\n###? v?[0-9[]")


def replace_section(changelog: str, heading: str, notes: str) -> str | None:
    start = changelog.find(heading)
    if start == -1:
        return None
    following = NEXT_VERSION_HEADING.search(changelog, start + len(heading))
    tail = changelog[following.start() :] if following else ""
    return f"{changelog[:start]}{notes.strip()}\n{tail}".rstrip("\n") + "\n"
