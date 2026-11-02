from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from release_notes.errors import NotEligibleError, NotesUnchangedError
from release_notes.github_client import GitHubClient
from release_notes.release_notes import published_notes
from release_notes.release_source import ReleaseSource, ReleaseSourceCollector


def collect(arguments: argparse.Namespace) -> None:
    collector = ReleaseSourceCollector(
        GitHubClient(), arguments.repository, arguments.configuration, arguments.manifest
    )
    try:
        if arguments.release_tag:
            source = collector.collect_past_release(arguments.previous_tag, arguments.release_tag)
        else:
            source = collector.collect()
    except NotEligibleError as reason:
        print(f"::notice::Keeping the release-please notes: {reason}")
        _write_output("state", "absent")
        return
    except NotesUnchangedError as unchanged:
        print(f"::notice::{unchanged}")
        _write_output("state", "unchanged")
        _write_output("pull-request", json.dumps(_described(unchanged.pull_request)))
        return
    arguments.source.write_text(source.to_json(), encoding="utf-8")
    _write_output("state", "ready")


def compose(arguments: argparse.Namespace) -> None:
    from release_notes.notes_writer import no_notes, write_notes

    source = ReleaseSource.from_json(arguments.source.read_text(encoding="utf-8"))
    written = write_notes(source) if source.commits else no_notes(source)
    arguments.notes.write_text(json.dumps(published_notes(written, source), ensure_ascii=False), encoding="utf-8")
    _write_output("notes-file", str(arguments.notes))


def preview(arguments: argparse.Namespace) -> None:
    source = ReleaseSource.from_json(arguments.source.read_text(encoding="utf-8"))
    notes = json.loads(arguments.notes.read_text(encoding="utf-8"))
    for changelog in notes["changelogs"]:
        print(f"# {source.repository} ({changelog['language']})\n\n{changelog['notes']}")
    print(notes["support"])


def _described(pull_request: dict) -> dict:
    return {
        "number": pull_request["number"],
        "title": pull_request["title"],
        "headBranchName": pull_request["head"]["ref"],
        "baseBranchName": pull_request["base"]["ref"],
    }


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
    collect_command.add_argument("--configuration", required=True)
    collect_command.add_argument("--manifest", required=True)
    collect_command.add_argument("--previous-tag", default="")
    collect_command.add_argument("--release-tag", default="")
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

    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
