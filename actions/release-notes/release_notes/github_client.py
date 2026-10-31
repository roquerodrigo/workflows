from __future__ import annotations

import json
import subprocess


class GitHubClient:
    """Reaches the REST API through `gh`, which reads its token from GH_TOKEN."""

    def get(self, path: str):
        return json.loads(self._run(["gh", "api", path]))

    def get_or_none(self, path: str):
        completed = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            return json.loads(completed.stdout)
        if "HTTP 404" in completed.stderr:
            return None
        raise RuntimeError(f"gh api {path} failed: {completed.stderr.strip()[:200]}")

    def file_text(self, repository: str, path: str, ref: str) -> str | None:
        completed = subprocess.run(
            [
                "gh",
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{repository}/contents/{path}?ref={ref}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout
        if "HTTP 404" in completed.stderr:
            return None
        raise RuntimeError(f"reading {path} failed: {completed.stderr.strip()[:200]}")

    def compared_commits(self, repository: str, base: str, head: str) -> list[dict]:
        commits: list[dict] = []
        page = 1
        while True:
            comparison = self.get(f"repos/{repository}/compare/{base}...{head}?per_page=100&page={page}")
            commits.extend(comparison["commits"])
            if len(commits) >= comparison["total_commits"] or not comparison["commits"]:
                return commits
            page += 1

    def update_pull_request_body(self, repository: str, number: int, body: str) -> None:
        self._run(
            ["gh", "api", "-X", "PATCH", f"repos/{repository}/pulls/{number}", "--input", "-"],
            stdin=json.dumps({"body": body}),
        )

    @staticmethod
    def _run(command: list[str], stdin: str | None = None) -> str:
        completed = subprocess.run(command, input=stdin, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{' '.join(command[:3])} failed: {completed.stderr.strip()[:200]}")
        return completed.stdout
