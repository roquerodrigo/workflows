from __future__ import annotations

import re
from dataclasses import dataclass

from release_notes.errors import NotEligibleError

NOTES_DELIMITER = "---"
HEADING = re.compile(r"^#{2,} \[?\d+\.\d+\.\d+[^\]]*\]?")
PREVIOUS_TAG = re.compile(r"/compare/(?P<tag>.+?)\.\.\.")


@dataclass(frozen=True)
class ReleasePullRequestBody:
    """The layout release-please parses back when it publishes the release."""

    before_notes: str
    heading: str
    after_notes: str

    @classmethod
    def parse(cls, body: str) -> ReleasePullRequestBody:
        lines = body.strip().replace("\r\n", "\n").split("\n")
        if NOTES_DELIMITER not in lines:
            raise NotEligibleError("the body has no notes delimiter")
        first = lines.index(NOTES_DELIMITER)
        last = len(lines) - 1 - lines[::-1].index(NOTES_DELIMITER)
        if last == first:
            raise NotEligibleError("the body has a single notes delimiter")
        notes = "\n".join(lines[first + 1 : last]).strip()
        if "<details" in notes:
            raise NotEligibleError("the body describes several packages")
        heading = notes.split("\n", 1)[0]
        if HEADING.match(heading) is None:
            raise NotEligibleError("the notes do not start with a version heading")
        return cls(
            before_notes="\n".join(lines[: first + 1]),
            heading=heading,
            after_notes="\n".join(lines[last:]),
        )

    @property
    def previous_tag(self) -> str:
        match = PREVIOUS_TAG.search(self.heading)
        if match is None:
            raise NotEligibleError("the first release has no previous tag to compare with")
        return match["tag"]

    def with_notes(self, notes: str) -> str:
        return f"{self.before_notes}\n\n\n{notes.strip()}\n\n{self.after_notes}"
