from __future__ import annotations

import re
from dataclasses import dataclass

from release_notes.errors import RejectedNotesError

CATEGORIES = ("breaking", "added", "changed", "fixed")
TITLES = {
    "en": {"breaking": "Breaking changes", "added": "New features", "changed": "Improvements", "fixed": "Bug fixes"},
    "pt-BR": {"breaking": "Mudanças incompatíveis", "added": "Novidades", "changed": "Melhorias", "fixed": "Correções"},
}
NO_USER_FACING_CHANGES = {
    "en": "Internal maintenance only, with no changes for those who use the project.",
    "pt-BR": "Apenas manutenção interna, sem mudanças para quem usa o projeto.",
}
SUPPORT_SECTIONS = {
    "en": (
        "### Support\n\nThis project is built and maintained on personal time. If it is useful to you, consider "
        "[sponsoring the work]({url}) — it keeps the development, the testing and the releases coming.\n"
    ),
    "pt-BR": (
        "### Apoio\n\nEste projeto é desenvolvido e mantido em tempo pessoal. Se ele for útil para você, considere "
        "[apoiar o trabalho]({url}) — isso mantém o desenvolvimento, os testes e os releases em andamento.\n"
    ),
}
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

    @classmethod
    def validated(cls, written: dict, known_pull_requests: set[int], *, has_breaking_commit: bool) -> ReleaseNotes:
        summary = _single_line(written["summary"])
        entries = tuple(
            NotesEntry(
                category=entry["category"],
                text=_single_line(entry["text"]),
                pull_requests=tuple(number for number in entry["pull_requests"] if number in known_pull_requests),
            )
            for entry in written["entries"]
        )
        if any(not entry.text or entry.category not in CATEGORIES for entry in entries):
            raise RejectedNotesError("an entry is empty or has an unknown category")
        if any(FORBIDDEN_MARKUP.search(text) for text in (summary, *(entry.text for entry in entries))):
            raise RejectedNotesError("the text carries a link, an image, a mention or a release-please tag")
        if has_breaking_commit and not any(entry.category == "breaking" for entry in entries):
            raise RejectedNotesError("a breaking commit has no breaking entry")
        return cls(summary=summary, entries=entries)

    def render(self, heading: str, language: str, repository: str) -> str:
        if not self.entries:
            return f"{heading}\n\n{NO_USER_FACING_CHANGES[language]}\n"
        blocks = [heading]
        if self.summary:
            blocks.append(self.summary)
        for category in CATEGORIES:
            lines = [_bullet(entry, repository) for entry in self.entries if entry.category == category]
            if lines:
                blocks.append(f"### {TITLES[language][category]}\n\n" + "\n".join(lines))
        return "\n\n".join(blocks) + "\n"


def support_section(language: str, repository: str) -> str:
    owner = repository.split("/")[0]
    return SUPPORT_SECTIONS[language].format(url=f"https://github.com/sponsors/{owner}")


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _bullet(entry: NotesEntry, repository: str) -> str:
    links = ", ".join(f"[#{number}](https://github.com/{repository}/pull/{number})" for number in entry.pull_requests)
    return f"- {entry.text} ({links})" if links else f"- {entry.text}"
