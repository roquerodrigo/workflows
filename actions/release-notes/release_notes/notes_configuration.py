from __future__ import annotations

import tomllib
from dataclasses import dataclass, field

from release_notes.errors import InvalidNotesConfigurationError

NOTES_CONFIGURATION_PATH = ".github/release-notes.toml"
BREAKING_SECTION = "breaking"
DEFAULT_SECTION_TITLES = {
    "en": {
        BREAKING_SECTION: "Breaking changes",
        "added": "New features",
        "changed": "Improvements",
        "fixed": "Bug fixes",
    },
    "pt-BR": {
        BREAKING_SECTION: "Mudanças incompatíveis",
        "added": "Novidades",
        "changed": "Melhorias",
        "fixed": "Correções",
    },
}
KNOWN_FIELDS = frozenset({"prompt", "sections", "priority_paths"})


def _is_filled_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class NotesConfiguration:
    section_titles: dict[str, str]
    prompt: str = ""
    priority_paths: list[str] = field(default_factory=list)

    @classmethod
    def of(cls, text: str | None, language: str) -> NotesConfiguration:
        declared = tomllib.loads(text) if text else {}
        unknown = sorted(set(declared) - KNOWN_FIELDS)
        if unknown:
            raise InvalidNotesConfigurationError(f"unknown fields: {', '.join(unknown)}")
        prompt = declared.get("prompt", "")
        if not isinstance(prompt, str):
            raise InvalidNotesConfigurationError("prompt is not text")
        priority_paths = declared.get("priority_paths", [])
        if not isinstance(priority_paths, list) or not all(_is_filled_text(path) for path in priority_paths):
            raise InvalidNotesConfigurationError("priority_paths is not a list of paths")
        return cls(
            section_titles=cls._section_titles(declared.get("sections", {}), language),
            prompt=prompt.strip(),
            priority_paths=priority_paths,
        )

    @staticmethod
    def _section_titles(declared: object, language: str) -> dict[str, str]:
        defaults = DEFAULT_SECTION_TITLES[language]
        if not isinstance(declared, dict) or not all(_is_filled_text(title) for title in declared.values()):
            raise InvalidNotesConfigurationError("sections does not map each section to its title")
        if not declared:
            return defaults
        # A breaking commit always needs an entry, so this section is there whatever the project declares.
        return {BREAKING_SECTION: defaults[BREAKING_SECTION], **declared}

    def is_priority(self, path: str) -> bool:
        return path.startswith(tuple(self.priority_paths))
