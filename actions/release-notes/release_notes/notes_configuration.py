from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import PurePosixPath

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
DEFAULT_NO_USER_FACING_CHANGES = {
    "en": "Internal maintenance only, with no changes for those who use the project.",
    "pt-BR": "Apenas manutenção interna, sem mudanças para quem usa o projeto.",
}
DEFAULT_SUPPORT_SECTIONS = {
    "en": (
        "### Support\n\nThis project is built and maintained on personal time. If it is useful to you, consider "
        "[sponsoring the work]({url}) — it keeps the development, the testing and the releases coming.\n"
    ),
    "pt-BR": (
        "### Apoio\n\nEste projeto é desenvolvido e mantido em tempo pessoal. Se ele for útil para você, considere "
        "[apoiar o trabalho]({url}) — isso mantém o desenvolvimento, os testes e os releases em andamento.\n"
    ),
}
KNOWN_FIELDS = frozenset({"language", "prompt", "sections", "priority_paths", "changelogs", "title", "bold_entries"})
KNOWN_CHANGELOG_FIELDS = frozenset(
    {"language", "path", "release_path", "sections", "no_user_facing_changes", "support"}
)
RELEASE_PATH_VERSION = "{version}"
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]+)*$")


def _is_filled_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class Changelog:
    """One language of the notes and the files that keep it. An empty path leaves the file to release-please."""

    language: str
    section_titles: dict[str, str]
    no_user_facing_changes: str
    support: str
    path: str = ""
    release_path: str = ""

    @classmethod
    def of(cls, declared: object) -> Changelog:
        if not isinstance(declared, dict):
            raise InvalidNotesConfigurationError("a changelog is not a table")
        unknown = sorted(set(declared) - KNOWN_CHANGELOG_FIELDS)
        if unknown:
            raise InvalidNotesConfigurationError(f"unknown changelog fields: {', '.join(unknown)}")
        language = declared.get("language")
        if not isinstance(language, str) or LANGUAGE_TAG.match(language) is None:
            raise InvalidNotesConfigurationError("language is not a language tag")
        return cls(
            language=language,
            section_titles=cls._section_titles(declared.get("sections", {}), language),
            no_user_facing_changes=cls._text(declared, "no_user_facing_changes", DEFAULT_NO_USER_FACING_CHANGES),
            support=cls._text(declared, "support", DEFAULT_SUPPORT_SECTIONS),
            path=cls._path(declared.get("path", "")),
            release_path=cls._release_path(declared.get("release_path", "")),
        )

    @staticmethod
    def _section_titles(declared: object, language: str) -> dict[str, str]:
        defaults = DEFAULT_SECTION_TITLES.get(language, {})
        if not isinstance(declared, dict) or not all(_is_filled_text(title) for title in declared.values()):
            raise InvalidNotesConfigurationError("sections does not map each section to its title")
        if not declared and not defaults:
            raise InvalidNotesConfigurationError(f"{language} has no built-in sections, so it must declare them")
        if not declared:
            return defaults
        if BREAKING_SECTION not in declared and BREAKING_SECTION not in defaults:
            raise InvalidNotesConfigurationError(f"{language} has no built-in title for the breaking section")
        # A breaking commit always needs an entry, so this section is there whatever the project declares.
        return {BREAKING_SECTION: defaults.get(BREAKING_SECTION), **declared}

    @staticmethod
    def _text(declared: dict, name: str, defaults: dict[str, str]) -> str:
        language = declared["language"]
        text = declared.get(name, defaults.get(language))
        if not _is_filled_text(text):
            raise InvalidNotesConfigurationError(f"{language} has no built-in {name}, so it must declare it")
        return text

    @staticmethod
    def _path(path: object) -> str:
        if not isinstance(path, str):
            raise InvalidNotesConfigurationError("path is not text")
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise InvalidNotesConfigurationError(f"{path} is outside the repository")
        return path

    @classmethod
    def _release_path(cls, release_path: object) -> str:
        path = cls._path(release_path)
        if path and RELEASE_PATH_VERSION not in path:
            raise InvalidNotesConfigurationError(
                f"release_path needs {RELEASE_PATH_VERSION}, or every release overwrites the last"
            )
        return path

    def support_section(self, repository: str) -> str:
        owner = repository.split("/")[0]
        return self.support.replace("{url}", f"https://github.com/sponsors/{owner}")


@dataclass(frozen=True)
class NotesConfiguration:
    changelogs: tuple[Changelog, ...]
    prompt: str = ""
    priority_paths: list[str] = field(default_factory=list)
    title: bool = False
    bold_entries: bool = False

    @classmethod
    def of(cls, text: str | None, default_language: str) -> NotesConfiguration:
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
        title = declared.get("title", False)
        bold_entries = declared.get("bold_entries", False)
        if not isinstance(title, bool) or not isinstance(bold_entries, bool):
            raise InvalidNotesConfigurationError("title and bold_entries are not true or false")
        return cls(
            changelogs=cls._changelogs(declared, default_language),
            prompt=prompt.strip(),
            priority_paths=priority_paths,
            title=title,
            bold_entries=bold_entries,
        )

    @classmethod
    def from_dict(cls, data: dict) -> NotesConfiguration:
        changelogs = tuple(Changelog(**changelog) for changelog in data["changelogs"])
        return cls(
            changelogs=changelogs,
            prompt=data["prompt"],
            priority_paths=data["priority_paths"],
            title=data["title"],
            bold_entries=data["bold_entries"],
        )

    @classmethod
    def _changelogs(cls, declared: dict, default_language: str) -> tuple[Changelog, ...]:
        if "changelogs" not in declared:
            language = declared.get("language", default_language)
            if language not in DEFAULT_SECTION_TITLES:
                raise InvalidNotesConfigurationError(f"language must be one of: {', '.join(DEFAULT_SECTION_TITLES)}")
            return (Changelog.of({"language": language, "sections": declared.get("sections", {})}),)
        if "language" in declared or "sections" in declared:
            raise InvalidNotesConfigurationError("language and sections belong inside each changelog")
        entries = declared["changelogs"]
        if not isinstance(entries, list) or not entries:
            raise InvalidNotesConfigurationError("changelogs is not a list of tables")
        changelogs = tuple(Changelog.of(entry) for entry in entries)
        cls._check_translations(changelogs)
        return changelogs

    @staticmethod
    def _check_translations(changelogs: tuple[Changelog, ...]) -> None:
        primary, *translations = changelogs
        if any(not translation.path and not translation.release_path for translation in translations):
            raise InvalidNotesConfigurationError("only the first changelog can leave out both of its paths")
        paths = [path for changelog in changelogs for path in (changelog.path, changelog.release_path) if path]
        languages = [changelog.language for changelog in changelogs]
        if len(set(paths)) != len(paths) or len(set(languages)) != len(languages):
            raise InvalidNotesConfigurationError("each changelog needs its own language and path")
        if any(set(translation.section_titles) != set(primary.section_titles) for translation in translations):
            raise InvalidNotesConfigurationError("every changelog must have the same sections")

    @property
    def primary(self) -> Changelog:
        return self.changelogs[0]

    @property
    def language(self) -> str:
        return self.primary.language

    @property
    def section_titles(self) -> dict[str, str]:
        return self.primary.section_titles

    @property
    def languages(self) -> list[str]:
        return [changelog.language for changelog in self.changelogs]

    def is_priority(self, path: str) -> bool:
        return path.startswith(tuple(self.priority_paths))
