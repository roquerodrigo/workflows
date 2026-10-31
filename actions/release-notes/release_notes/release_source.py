from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from release_notes.conventional_commit import ConventionalCommit, visible_types
from release_notes.errors import NotEligibleError
from release_notes.github_client import GitHubClient
from release_notes.pull_request_body import ReleasePullRequestBody

RELEASE_BRANCH_PREFIX = "release-please--"
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
    pull_request_number: int
    head_sha: str
    head_branch: str
    language: str
    changelog_path: str
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
        return cls(**data, commits=commits)


def language_of(hacs_manifest: str | None) -> str:
    country = json.loads(hacs_manifest).get("country") if hacs_manifest else None
    return "pt-BR" if country in ("BR", ["BR"]) else "en"


def is_bot(login: str | None) -> bool:
    return login is None or login.endswith("[bot]")


class ReleaseSourceCollector:
    def __init__(self, github: GitHubClient, repository: str, configuration_path: str) -> None:
        self._github = github
        self._repository = repository
        self._configuration_path = configuration_path

    def collect(self, pull_request_number: int) -> ReleaseSource:
        pull_request = self._github.get(f"repos/{self._repository}/pulls/{pull_request_number}")
        head_branch = pull_request["head"]["ref"]
        if not head_branch.startswith(RELEASE_BRANCH_PREFIX):
            raise NotEligibleError(f"{head_branch} is not a release branch")
        body = ReleasePullRequestBody.parse(pull_request["body"] or "")
        head_sha = pull_request["head"]["sha"]
        released_sha = self._github.get(f"repos/{self._repository}/commits/{head_sha}")["parents"][0]["sha"]
        root, package = self._configuration(released_sha)
        shown_types = visible_types(package, root)
        commits = [
            self._release_commit(commit["sha"])
            for commit in self._github.compared_commits(self._repository, body.previous_tag, released_sha)
            if self._is_shown(commit["commit"]["message"], shown_types)
        ]
        return ReleaseSource(
            repository=self._repository,
            pull_request_number=pull_request_number,
            head_sha=head_sha,
            head_branch=head_branch,
            language=language_of(self._github.file_text(self._repository, "hacs.json", released_sha)),
            changelog_path=package.get("changelog-path") or root.get("changelog-path") or "CHANGELOG.md",
            commits=commits,
        )

    def _configuration(self, ref: str) -> tuple[dict, dict]:
        text = self._github.file_text(self._repository, self._configuration_path, ref)
        if text is None:
            raise NotEligibleError(f"{self._configuration_path} does not exist")
        root = json.loads(text)
        packages = root.get("packages", {})
        if len(packages) != 1:
            raise NotEligibleError("only single-package repositories are supported")
        return root, next(iter(packages.values()))

    @staticmethod
    def _is_shown(message: str, shown_types: frozenset[str]) -> bool:
        commit = ConventionalCommit.parse(message)
        return commit is not None and (commit.is_breaking or commit.type in shown_types)

    def _release_commit(self, sha: str) -> ReleaseCommit:
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
            files=self._files(details.get("files", []), written_by_a_bot),
        )

    @staticmethod
    def _description(pull_request: dict | None, written_by_a_bot: bool) -> str:
        if pull_request is None or written_by_a_bot:
            return ""
        return (pull_request.get("body") or "")[:MAXIMUM_DESCRIPTION_CHARACTERS]

    @staticmethod
    def _files(files: list[dict], written_by_a_bot: bool) -> list[ChangedFile]:
        remaining = 0 if written_by_a_bot else MAXIMUM_PATCH_CHARACTERS_PER_COMMIT
        changed = []
        for file in files:
            is_generated = file["filename"].endswith(GENERATED_FILES)
            patch = "" if is_generated else file.get("patch", "")[: min(MAXIMUM_PATCH_CHARACTERS_PER_FILE, remaining)]
            remaining -= len(patch)
            changed.append(ChangedFile(file["filename"], file["additions"], file["deletions"], patch))
        return changed
