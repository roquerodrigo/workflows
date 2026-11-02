from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from release_notes.conventional_commit import ConventionalCommit, visible_types
from release_notes.errors import NotEligibleError, NotesUnchangedError
from release_notes.github_client import GitHubClient
from release_notes.notes_configuration import NOTES_CONFIGURATION_PATH, NotesConfiguration

RELEASE_BRANCH_PREFIX = "release-please--"
DIGEST_MARKER = re.compile(r"<!-- release-notes: (?P<digest>[0-9a-f]{64}) -->")
MAXIMUM_PATCH_CHARACTERS_PER_FILE = 4_000
MAXIMUM_PATCH_CHARACTERS_PER_COMMIT = 20_000
MAXIMUM_DESCRIPTION_CHARACTERS = 6_000
GENERATED_FILES = ("uv.lock", "package-lock.json", "CHANGELOG.md")


@dataclass(frozen=True)
class ChangedFile:
    path: str
    additions: int
    deletions: int
    patch: str


@dataclass(frozen=True)
class ReleaseCommit:
    message: str
    is_breaking: bool
    pull_request_number: int | None
    pull_request_title: str
    pull_request_description: str
    files: list[ChangedFile]


@dataclass(frozen=True)
class ReleaseSource:
    repository: str
    digest: str
    notes_configuration: NotesConfiguration
    commits: list[ReleaseCommit]

    @property
    def known_pull_requests(self) -> set[int]:
        return {commit.pull_request_number for commit in self.commits if commit.pull_request_number is not None}

    @property
    def has_breaking_commit(self) -> bool:
        return any(commit.is_breaking for commit in self.commits)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> ReleaseSource:
        data = json.loads(text)
        commits = [
            ReleaseCommit(**{**commit, "files": [ChangedFile(**file) for file in commit["files"]]})
            for commit in data.pop("commits")
        ]
        notes_configuration = NotesConfiguration.from_dict(data.pop("notes_configuration"))
        return cls(**data, notes_configuration=notes_configuration, commits=commits)


@dataclass(frozen=True)
class SourceFiles:
    configuration: str
    root: dict
    package: dict
    package_path: str
    notes: str | None
    hacs_manifest: str | None


def notes_digest(source_files: SourceFiles, commit_shas: list[str]) -> str:
    material = "\n".join([source_files.configuration, source_files.notes or "", *commit_shas])
    return hashlib.sha256(material.encode()).hexdigest()


def digest_in(pull_request_body: str | None) -> str | None:
    match = DIGEST_MARKER.search(pull_request_body or "")
    return match["digest"] if match else None


def language_of(hacs_manifest: str | None) -> str:
    country = json.loads(hacs_manifest).get("country") if hacs_manifest else None
    return "pt-BR" if country in ("BR", ["BR"]) else "en"


def is_bot(login: str | None) -> bool:
    return login is None or login.endswith("[bot]")


class ReleaseSourceCollector:
    def __init__(self, github: GitHubClient, repository: str, configuration_path: str, manifest_path: str) -> None:
        self._github = github
        self._repository = repository
        self._configuration_path = configuration_path
        self._manifest_path = manifest_path

    def collect(self) -> ReleaseSource:
        details = self._github.get(f"repos/{self._repository}")
        head_sha = self._github.get(f"repos/{self._repository}/commits/{details['default_branch']}")["sha"]
        source_files = self._source_files(head_sha)
        previous_tag = self._previous_tag(source_files, head_sha)
        shown = self._shown_commits(source_files, previous_tag, head_sha)
        digest = notes_digest(source_files, [commit["sha"] for commit in shown])
        open_pull_request = self._open_release_pull_request()
        if open_pull_request is not None and digest_in(open_pull_request.get("body")) == digest:
            raise NotesUnchangedError(open_pull_request)
        return self._source(source_files, shown, digest)

    def collect_past_release(self, previous_tag: str, release_tag: str) -> ReleaseSource:
        release_commit = self._github.get(f"repos/{self._repository}/commits/{release_tag}")
        released_sha = release_commit["parents"][0]["sha"]
        source_files = self._source_files(released_sha)
        shown = self._shown_commits(source_files, previous_tag, released_sha)
        return self._source(source_files, shown, notes_digest(source_files, [commit["sha"] for commit in shown]))

    def _source_files(self, ref: str) -> SourceFiles:
        configuration = self._github.file_text(self._repository, self._configuration_path, ref)
        if configuration is None:
            raise NotEligibleError(f"{self._configuration_path} does not exist")
        root = json.loads(configuration)
        packages = root.get("packages", {})
        if len(packages) != 1:
            raise NotEligibleError("only single-package repositories are supported")
        return SourceFiles(
            configuration=configuration,
            root=root,
            package=next(iter(packages.values())),
            package_path=next(iter(packages)),
            notes=self._github.file_text(self._repository, NOTES_CONFIGURATION_PATH, ref),
            hacs_manifest=self._github.file_text(self._repository, "hacs.json", ref),
        )

    def _previous_tag(self, source_files: SourceFiles, ref: str) -> str:
        if source_files.root.get("include-component-in-tag", True):
            raise NotEligibleError("tags that carry a component are not supported")
        manifest = self._github.file_text(self._repository, self._manifest_path, ref)
        version = json.loads(manifest or "{}").get(source_files.package_path)
        prefix = "v" if source_files.root.get("include-v-in-tag", True) else ""
        tag = f"{prefix}{version}"
        if version is None or self._github.get_or_none(f"repos/{self._repository}/git/ref/tags/{tag}") is None:
            raise NotEligibleError("the first release has no previous tag to compare with")
        return tag

    def _shown_commits(self, source_files: SourceFiles, previous_tag: str, head_sha: str) -> list[dict]:
        shown_types = visible_types(source_files.package, source_files.root)
        return [
            commit
            for commit in self._github.compared_commits(self._repository, previous_tag, head_sha)
            if self._is_shown(commit["commit"]["message"], shown_types)
        ]

    def _open_release_pull_request(self) -> dict | None:
        pull_requests = self._github.get(f"repos/{self._repository}/pulls?state=open&per_page=100")
        return next(
            (item for item in pull_requests if item["head"]["ref"].startswith(RELEASE_BRANCH_PREFIX)),
            None,
        )

    def _source(self, source_files: SourceFiles, shown: list[dict], digest: str) -> ReleaseSource:
        notes_configuration = NotesConfiguration.of(source_files.notes, language_of(source_files.hacs_manifest))
        return ReleaseSource(
            repository=self._repository,
            digest=digest,
            notes_configuration=notes_configuration,
            commits=[self._release_commit(commit["sha"], notes_configuration) for commit in shown],
        )

    @staticmethod
    def _is_shown(message: str, shown_types: frozenset[str]) -> bool:
        commit = ConventionalCommit.parse(message)
        return commit is not None and (commit.is_breaking or commit.type in shown_types)

    def _release_commit(self, sha: str, notes_configuration: NotesConfiguration) -> ReleaseCommit:
        details = self._github.get(f"repos/{self._repository}/commits/{sha}")
        message = details["commit"]["message"]
        pull_requests = self._github.get(f"repos/{self._repository}/commits/{sha}/pulls")
        pull_request = next((item for item in pull_requests if item.get("merged_at")), None)
        written_by_a_bot = is_bot((details.get("author") or {}).get("login"))
        parsed = ConventionalCommit.parse(message)
        return ReleaseCommit(
            message=message,
            is_breaking=parsed.is_breaking if parsed else False,
            pull_request_number=pull_request["number"] if pull_request else None,
            pull_request_title=pull_request["title"] if pull_request else "",
            pull_request_description=self._description(pull_request, written_by_a_bot),
            files=self._files(details.get("files", []), written_by_a_bot, notes_configuration),
        )

    @staticmethod
    def _description(pull_request: dict | None, written_by_a_bot: bool) -> str:
        if pull_request is None or written_by_a_bot:
            return ""
        return (pull_request.get("body") or "")[:MAXIMUM_DESCRIPTION_CHARACTERS]

    @staticmethod
    def _files(files: list[dict], written_by_a_bot: bool, notes_configuration: NotesConfiguration) -> list[ChangedFile]:
        remaining = 0 if written_by_a_bot else MAXIMUM_PATCH_CHARACTERS_PER_COMMIT
        changed = []
        for file in sorted(files, key=lambda file: not notes_configuration.is_priority(file["filename"])):
            is_generated = file["filename"].endswith(GENERATED_FILES)
            patch = "" if is_generated else file.get("patch", "")
            if not notes_configuration.is_priority(file["filename"]):
                patch = patch[: min(MAXIMUM_PATCH_CHARACTERS_PER_FILE, remaining)]
                remaining -= len(patch)
            elif written_by_a_bot:
                patch = ""
            changed.append(ChangedFile(file["filename"], file["additions"], file["deletions"], patch))
        return changed
