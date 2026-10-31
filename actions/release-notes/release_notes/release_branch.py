from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path

from release_notes.errors import StalePullRequestError


class ReleaseBranch:
    """Amends the release commit, so a rebase merge still lands one commit on the default branch."""

    def __init__(self, work_tree: Path, token: str) -> None:
        self._work_tree = work_tree
        self._token = token

    def head(self) -> str:
        return self._git("rev-parse", "HEAD")

    def amend_and_push(self, branch: str, expected_head: str, relative_path: str, content: str) -> None:
        if self.head() != expected_head:
            raise StalePullRequestError(f"{branch} is no longer at {expected_head}")
        (self._work_tree / relative_path).write_text(content, encoding="utf-8")
        self._git("add", "--", relative_path)
        committer_name = self._git("log", "-1", "--format=%cn")
        committer_email = self._git("log", "-1", "--format=%ce")
        self._git(
            "-c",
            f"user.name={committer_name}",
            "-c",
            f"user.email={committer_email}",
            "commit",
            "--amend",
            "--no-edit",
            "--no-verify",
        )
        # The lease is what keeps a slower run from overwriting one that started after it.
        self._git(
            "push",
            f"--force-with-lease=refs/heads/{branch}:{expected_head}",
            "origin",
            f"HEAD:refs/heads/{branch}",
            authenticated=True,
        )

    def _git(self, *arguments: str, authenticated: bool = False) -> str:
        environment = {**os.environ, **(self._credentials() if authenticated else {})}
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self._work_tree,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"git {arguments[0]} failed: {completed.stderr.strip()[:300]}")
        return completed.stdout.strip()

    def _credentials(self) -> dict[str, str]:
        encoded = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
        return {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {encoded}",
        }
