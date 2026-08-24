"""Bring every repository's branch protection in line with branch-protection.json.

Branch protection is not something that drifts on its own — it goes missing.
A repository created after the convention was written simply never receives it,
which is how three of them ended up with an unprotected default branch while
their siblings required seven checks. So this reconciles the declared state and,
just as importantly, reports the repositories nobody has declared yet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.github.com"
MANAGED = ("checks", "strict", "require_pull_request", "enforce_admins", "allow_force_pushes", "allow_deletions")


class GitHub:
    def __init__(self, token: str) -> None:
        self._token = token

    def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(f"{API}{path}", data=body, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise RuntimeError(f"{method} {path} failed: {error.code} {error.read().decode()[:300]}") from error

    def owned_repositories(self) -> list[dict]:
        repositories: list[dict] = []
        page = 1
        while True:
            batch = self.request("GET", f"/user/repos?affiliation=owner&per_page=100&page={page}") or []
            repositories.extend(batch)
            if len(batch) < 100:
                return repositories
            page += 1


def desired_state(config: dict, name: str) -> dict:
    entry = config["repositories"][name]
    entry = {"profile": entry} if isinstance(entry, str) else dict(entry)
    profile = config["profiles"].get(entry.pop("profile", None), {})
    state = {**config["defaults"], "checks": profile.get("checks", [])}
    state.update({key: value for key, value in entry.items() if key in MANAGED})
    return state


def current_state(protection: dict | None) -> dict | None:
    if protection is None:
        return None
    checks = protection.get("required_status_checks") or {}
    return {
        "checks": checks.get("contexts", []),
        "strict": checks.get("strict", False),
        "require_pull_request": protection.get("required_pull_request_reviews") is not None,
        "enforce_admins": (protection.get("enforce_admins") or {}).get("enabled", False),
        "allow_force_pushes": (protection.get("allow_force_pushes") or {}).get("enabled", False),
        "allow_deletions": (protection.get("allow_deletions") or {}).get("enabled", False),
    }


def differences(current: dict | None, desired: dict) -> list[str]:
    if current is None:
        return ["no protection at all"]
    changed = []
    for key in MANAGED:
        before, after = current[key], desired[key]
        if key == "checks":
            before, after = sorted(before), sorted(after)
        if before != after:
            changed.append(f"{key}: {before!r} -> {after!r}")
    return changed


def payload_for(desired: dict) -> dict:
    reviews = {"required_approving_review_count": 0, "dismiss_stale_reviews": False}
    return {
        "required_status_checks": {"strict": desired["strict"], "contexts": desired["checks"]},
        "enforce_admins": desired["enforce_admins"],
        "required_pull_request_reviews": reviews if desired["require_pull_request"] else None,
        "restrictions": None,
        "allow_force_pushes": desired["allow_force_pushes"],
        "allow_deletions": desired["allow_deletions"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="branch-protection.json", type=Path)
    parser.add_argument("--apply", action="store_true", help="write the changes; without it nothing is modified")
    arguments = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is unset", file=sys.stderr)
        return 1

    config = json.loads(arguments.config.read_text())
    github = GitHub(token)
    owner = github.request("GET", "/user")["login"]

    applied, drifted, failed = [], [], []
    for name in sorted(config["repositories"]):
        desired = desired_state(config, name)
        branch = github.request("GET", f"/repos/{owner}/{name}")
        if branch is None:
            failed.append(f"{name}: repository not found")
            continue
        default_branch = branch["default_branch"]
        protection = github.request("GET", f"/repos/{owner}/{name}/branches/{default_branch}/protection")
        changed = differences(current_state(protection), desired)
        if not changed:
            continue
        drifted.append((name, changed))
        if arguments.apply:
            try:
                github.request("PUT", f"/repos/{owner}/{name}/branches/{default_branch}/protection", payload_for(desired))
                applied.append(name)
            except RuntimeError as error:
                failed.append(f"{name}: {error}")

    declared = set(config["repositories"])
    undeclared = sorted(
        repository["name"]
        for repository in github.owned_repositories()
        if not repository["fork"] and not repository["archived"] and not repository["private"]
        and repository["name"] not in declared
    )

    verb = "updated" if arguments.apply else "would update"
    print(f"## Branch protection ({'apply' if arguments.apply else 'report only'})\n")
    if drifted:
        print(f"{len(drifted)} repositories {verb}:\n")
        for name, changed in drifted:
            print(f"- **{name}**")
            for line in changed:
                print(f"  - {line}")
    else:
        print("Every declared repository already matches.")
    if undeclared:
        print(f"\n{len(undeclared)} public repositories are not declared and were left untouched:\n")
        print("\n".join(f"- {name}" for name in undeclared))
    if failed:
        print("\nFailures:\n")
        print("\n".join(f"- {line}" for line in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
