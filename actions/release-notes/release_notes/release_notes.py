from __future__ import annotations

import re
from dataclasses import dataclass

from release_notes.errors import RejectedNotesError
from release_notes.notes_configuration import BREAKING_SECTION, Changelog
from release_notes.release_source import ReleaseSource

BOLD_MARK = "**"
FORBIDDEN_MARKUP = re.compile(r"https?://|!\[|\]\(|<\s*/?\s*(details|summary)|(?<![\w.])@[\w-]+", re.IGNORECASE)


@dataclass(frozen=True)
class NotesEntry:
    category: str
    text: str
    pull_requests: tuple[int, ...]


@dataclass(frozen=True)
class ReleaseNotes:
    summary: str
    entries: tuple[NotesEntry, ...]
    title: str = ""

    @classmethod
    def validated(
        cls,
        written: dict,
        known_pull_requests: set[int],
        *,
        has_breaking_commit: bool,
        section_titles: dict[str, str],
        requires_title: bool = False,
        bold_entries: bool = False,
    ) -> ReleaseNotes:
        title = _single_line(written.get("title", ""))
        summary = _single_line(written["summary"])
        entries = tuple(
            NotesEntry(
                category=entry["category"],
                text=_single_line(entry["text"]),
                pull_requests=tuple(number for number in entry["pull_requests"] if number in known_pull_requests),
            )
            for entry in written["entries"]
        )
        if any(not entry.text or entry.category not in section_titles for entry in entries):
            raise RejectedNotesError("an entry is empty or has an unknown category")
        if any(FORBIDDEN_MARKUP.search(text) for text in (title, summary, *(entry.text for entry in entries))):
            raise RejectedNotesError("the text carries a link, an image or a mention")
        if requires_title and entries and not title:
            raise RejectedNotesError("a release with entries has no title")
        if BOLD_MARK in title:
            raise RejectedNotesError("the title carries bold of its own")
        if bold_entries and any(entry.text.count(BOLD_MARK) % 2 for entry in entries):
            raise RejectedNotesError("an entry leaves its bold open")
        if has_breaking_commit and not any(entry.category == BREAKING_SECTION for entry in entries):
            raise RejectedNotesError("a breaking commit has no breaking entry")
        return cls(summary=summary, entries=entries, title=title)

    def render(self, changelog: Changelog, repository: str) -> str:
        if not self.entries:
            return f"{changelog.no_user_facing_changes}\n"
        blocks = []
        if self.title:
            blocks.append(f"{BOLD_MARK}{self.title}{BOLD_MARK}")
        if self.summary:
            blocks.append(self.summary)
        for category, title in changelog.section_titles.items():
            lines = [_bullet(entry, repository) for entry in self.entries if entry.category == category]
            if lines:
                blocks.append(f"### {title}\n\n" + "\n".join(lines))
        return "\n\n".join(blocks) + "\n"


def published_notes(written: dict, source: ReleaseSource) -> dict:
    """What the release needs from this step. The version and the heading stay with release-please."""
    configuration = source.notes_configuration
    return {
        "digest": source.digest,
        "support": configuration.primary.support_section(source.repository),
        "changelogs": [
            {
                "language": changelog.language,
                "path": changelog.path,
                "release_path": changelog.release_path,
                "notes": _rendered(written, source, changelog),
            }
            for changelog in configuration.changelogs
        ],
    }


def _rendered(written: dict, source: ReleaseSource, changelog: Changelog) -> str:
    notes = ReleaseNotes.validated(
        _written_in(written, changelog.language),
        source.known_pull_requests,
        has_breaking_commit=source.has_breaking_commit,
        section_titles=changelog.section_titles,
        requires_title=source.notes_configuration.title,
        bold_entries=source.notes_configuration.bold_entries,
    )
    return notes.render(changelog, source.repository)


def _written_in(written: dict, language: str) -> dict:
    return {
        "title": written["title"][language] if "title" in written else "",
        "summary": written["summary"][language],
        "entries": [{**entry, "text": entry["text"][language]} for entry in written["entries"]],
    }


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _bullet(entry: NotesEntry, repository: str) -> str:
    links = ", ".join(f"[#{number}](https://github.com/{repository}/pull/{number})" for number in entry.pull_requests)
    return f"- {entry.text} ({links})" if links else f"- {entry.text}"
