"""Bring every repository in line with repository-policy.json.

Two kinds of setting live here, for the same reason: neither drifts on its own,
both go missing. A repository created after a convention was agreed never
receives it — which is how three integrations ended up with an unprotected
default branch, three others with secret scanning off, and three still accepting
a squash merge the release tooling does not expect. So this reconciles the
declared state and, just as importantly, reports the repositories nobody has
declared yet.
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
PROTECTION_KEYS = ("checks", "strict", "require_pull_request", "enforce_admins", "allow_force_pushes", "allow_deletions")
SECURITY_KEYS = ("secret_scanning", "secret_scanning_push_protection")


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
            raise RuntimeError(f"{method} {path} failed: {error.code} {error.read().decode()[:200]}") from error

    def owned_repositories(self) -> list[dict]:
        repositories: list[dict] = []
        page = 1
        while True:
            batch = self.request("GET", f"/user/repos?affiliation=owner&per_page=100&page={page}") or []
            repositories.extend(batch)
            if len(batch) < 100:
                return repositories
            page += 1


def declared_settings(config: dict) -> dict:
    return {key: value for key, value in config["settings"].items() if not key.startswith("$")}


def actual_settings(repository: dict, wanted: dict) -> dict:
    analysis = repository.get("security_and_analysis") or {}
    actual = {key: repository.get(key) for key in wanted if key not in SECURITY_KEYS}
    for key in SECURITY_KEYS:
        if key in wanted:
            actual[key] = (analysis.get(key) or {}).get("status")
    return actual


def desired_protection(config: dict, name: str) -> dict:
    entry = config["repositories"][name]
    entry = {"profile": entry} if isinstance(entry, str) else dict(entry)
    profile = config["profiles"].get(entry.pop("profile", None), {})
    state = {**config["protection_defaults"], "checks": profile.get("checks", [])}
    state.update({key: value for key, value in entry.items() if key in PROTECTION_KEYS})
    return state


def actual_protection(protection: dict | None) -> dict | None:
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


def differences(current: dict | None, desired: dict, keys: tuple[str, ...] | None = None) -> list[str]:
    if current is None:
        return ["no protection at all"]
    changed = []
    for key in keys or desired:
        before, after = current.get(key), desired[key]
        if key == "checks":
            before, after = sorted(before or []), sorted(after)
        if before != after:
            changed.append(f"{key}: {before!r} -> {after!r}")
    return changed


def protection_payload(desired: dict) -> dict:
    reviews = {"required_approving_review_count": 0, "dismiss_stale_reviews": False}
    return {
        "required_status_checks": {"strict": desired["strict"], "contexts": desired["checks"]},
        "enforce_admins": desired["enforce_admins"],
        "required_pull_request_reviews": reviews if desired["require_pull_request"] else None,
        "restrictions": None,
        "allow_force_pushes": desired["allow_force_pushes"],
        "allow_deletions": desired["allow_deletions"],
    }


def report(title: str, drifted: list[tuple[str, list[str]]], verb: str) -> None:
    print(f"\n### {title}\n")
    if not drifted:
        print("Every declared repository already matches.")
        return
    print(f"{len(drifted)} repositories {verb}:\n")
    for name, changed in drifted:
        print(f"- **{name}**")
        for line in changed:
            print(f"  - {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="repository-policy.json", type=Path)
    parser.add_argument("--apply", action="store_true", help="write the changes; without it nothing is modified")
    arguments = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is unset", file=sys.stderr)
        return 1

    config = json.loads(arguments.config.read_text())
    wanted_settings = declared_settings(config)
    github = GitHub(token)
    owner = github.request("GET", "/user")["login"]

    protection_drift, settings_drift, failed = [], [], []
    for name in sorted(config["repositories"]):
        repository = github.request("GET", f"/repos/{owner}/{name}")
        if repository is None:
            failed.append(f"{name}: repository not found")
            continue

        changed = differences(actual_settings(repository, wanted_settings), wanted_settings)
        if changed:
            settings_drift.append((name, changed))
            if arguments.apply:
                plain = {key: value for key, value in wanted_settings.items() if key not in SECURITY_KEYS}
                security = {key: {"status": wanted_settings[key]} for key in SECURITY_KEYS if key in wanted_settings}
                for payload in (plain, {"security_and_analysis": security} if security else None):
                    if not payload:
                        continue
                    try:
                        github.request("PATCH", f"/repos/{owner}/{name}", payload)
                    except RuntimeError as error:
                        failed.append(f"{name}: {error}")

        branch = repository["default_branch"]
        protection = github.request("GET", f"/repos/{owner}/{name}/branches/{branch}/protection")
        desired = desired_protection(config, name)
        changed = differences(actual_protection(protection), desired, PROTECTION_KEYS)
        if changed:
            protection_drift.append((name, changed))
            if arguments.apply:
                try:
                    github.request("PUT", f"/repos/{owner}/{name}/branches/{branch}/protection", protection_payload(desired))
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
    print(f"## Repository policy ({'apply' if arguments.apply else 'report only'})")
    report("Settings", settings_drift, verb)
    report("Branch protection", protection_drift, verb)
    if undeclared:
        print(f"\n### Not declared\n\n{len(undeclared)} public repositories were left untouched:\n")
        print("\n".join(f"- {name}" for name in undeclared))
    if failed:
        print("\n### Failures\n")
        print("\n".join(f"- {line}" for line in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
