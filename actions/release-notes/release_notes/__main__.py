from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from release_notes.changelog import replace_section
from release_notes.errors import NotEligibleError, StalePullRequestError
from release_notes.github_client import GitHubClient
from release_notes.pull_request_body import ReleasePullRequestBody
from release_notes.release_branch import ReleaseBranch
from release_notes.release_notes import ReleaseNotes, support_section
from release_notes.release_source import ReleaseSource, ReleaseSourceCollector


def collect(arguments: argparse.Namespace) -> None:
    collector = ReleaseSourceCollector(GitHubClient(), arguments.repository, arguments.configuration)
    try:
        source = collector.collect(arguments.pull_request)
    except NotEligibleError as reason:
        print(f"::notice::Keeping the release-please notes: {reason}")
        _write_output("eligible", "false")
        return
    arguments.source.write_text(source.to_json(), encoding="utf-8")
    _write_output("eligible", "true")


def compose(arguments: argparse.Namespace) -> None:
    from release_notes.notes_writer import write_notes

    source = ReleaseSource.from_json(arguments.source.read_text(encoding="utf-8"))
    written = write_notes(source) if source.commits else {"summary": "", "entries": []}
    ReleaseNotes.validated(written, source.known_pull_requests, has_breaking_commit=source.has_breaking_commit)
    arguments.notes.write_text(json.dumps(written, ensure_ascii=False), encoding="utf-8")


def _rendered(source: ReleaseSource, heading: str, notes_path: Path) -> str:
    notes = ReleaseNotes.validated(
        json.loads(notes_path.read_text(encoding="utf-8")),
        source.known_pull_requests,
        has_breaking_commit=source.has_breaking_commit,
    )
    return notes.render(heading, source.language, source.repository)


def preview(arguments: argparse.Namespace) -> None:
    source = ReleaseSource.from_json(arguments.source.read_text(encoding="utf-8"))
    pull_request = GitHubClient().get(f"repos/{source.repository}/pulls/{source.pull_request_number}")
    body = ReleasePullRequestBody.parse(pull_request["body"] or "")
    rendered = _rendered(source, body.heading, arguments.notes)
    published = f"{rendered}\n{support_section(source.language, source.repository)}"
    print(f"# {source.repository} #{source.pull_request_number} ({source.language})\n\n{published}")


def apply(arguments: argparse.Namespace) -> None:
    github = GitHubClient()
    source = ReleaseSource.from_json(arguments.source.read_text(encoding="utf-8"))
    pull_request = github.get(f"repos/{source.repository}/pulls/{source.pull_request_number}")
    if pull_request["head"]["sha"] != source.head_sha:
        print(f"::notice::Skipping: {source.head_branch} moved while the notes were being written")
        return
    body = ReleasePullRequestBody.parse(pull_request["body"] or "")
    rendered = _rendered(source, body.heading, arguments.notes)
    changelog_path = arguments.work_tree / source.changelog_path
    existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else None
    updated = replace_section(existing, body.heading, rendered) if existing else None
    if updated is None:
        print(f"::warning::{source.changelog_path} has no section for this release; only the body was rewritten")
    else:
        branch = ReleaseBranch(arguments.work_tree, os.environ["GH_TOKEN"])
        try:
            branch.amend_and_push(source.head_branch, source.head_sha, source.changelog_path, updated)
        except StalePullRequestError as reason:
            print(f"::notice::Skipping: {reason}")
            return
    published = f"{rendered}\n{support_section(source.language, source.repository)}"
    github.update_pull_request_body(source.repository, source.pull_request_number, body.with_notes(published))


def _write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="release_notes")
    commands = parser.add_subparsers(dest="command", required=True)

    collect_command = commands.add_parser("collect")
    collect_command.add_argument("--repository", required=True)
    collect_command.add_argument("--pull-request", required=True, type=int)
    collect_command.add_argument("--configuration", required=True)
    collect_command.add_argument("--source", required=True, type=Path)
    collect_command.set_defaults(handler=collect)

    compose_command = commands.add_parser("compose")
    compose_command.add_argument("--source", required=True, type=Path)
    compose_command.add_argument("--notes", required=True, type=Path)
    compose_command.set_defaults(handler=compose)

    preview_command = commands.add_parser("preview")
    preview_command.add_argument("--source", required=True, type=Path)
    preview_command.add_argument("--notes", required=True, type=Path)
    preview_command.set_defaults(handler=preview)

    apply_command = commands.add_parser("apply")
    apply_command.add_argument("--source", required=True, type=Path)
    apply_command.add_argument("--notes", required=True, type=Path)
    apply_command.add_argument("--work-tree", required=True, type=Path)
    apply_command.set_defaults(handler=apply)

    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
