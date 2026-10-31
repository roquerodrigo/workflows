import subprocess
import tempfile
import unittest
from pathlib import Path

from release_notes.errors import StalePullRequestError
from release_notes.release_branch import ReleaseBranch

BRANCH = "release-please--branches--main"


def git(directory, *arguments):
    completed = subprocess.run(["git", *arguments], cwd=directory, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


class ReleaseBranchTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.remote = root / "remote.git"
        self.clone = root / "clone"
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.clone)], check=True, capture_output=True)
        git(self.clone, "config", "user.name", "release-please")
        git(self.clone, "config", "user.email", "release@example.com")
        git(self.clone, "switch", "-c", BRANCH)
        (self.clone / "CHANGELOG.md").write_text("old\n", encoding="utf-8")
        git(self.clone, "add", ".")
        git(self.clone, "commit", "-m", "base")
        (self.clone / "CHANGELOG.md").write_text("generated\n", encoding="utf-8")
        git(self.clone, "commit", "-am", "chore(main): release 1.0.0")
        git(self.clone, "push", "-q", "origin", BRANCH)
        self.head = git(self.clone, "rev-parse", "HEAD")
        self.branch = ReleaseBranch(self.clone, "token")

    def test_amending_keeps_one_commit_with_the_same_message(self):
        self.branch.amend_and_push(BRANCH, self.head, "CHANGELOG.md", "rewritten\n")
        self.assertEqual(git(self.remote, "log", BRANCH, "--format=%s"), "chore(main): release 1.0.0\nbase")
        self.assertEqual(git(self.remote, "show", f"{BRANCH}:CHANGELOG.md"), "rewritten")

    def test_refuses_a_checkout_behind_the_expected_head(self):
        with self.assertRaises(StalePullRequestError):
            self.branch.amend_and_push(BRANCH, "0" * 40, "CHANGELOG.md", "rewritten\n")

    def test_the_lease_refuses_a_branch_that_moved_on_the_remote(self):
        other = self.clone.parent / "other"
        subprocess.run(
            ["git", "clone", "-q", "-b", BRANCH, str(self.remote), str(other)], check=True, capture_output=True
        )
        git(other, "config", "user.name", "someone")
        git(other, "config", "user.email", "someone@example.com")
        git(other, "commit", "--allow-empty", "-m", "newer")
        git(other, "push", "-q", "origin", BRANCH)
        git(self.clone, "fetch", "-q", "origin")
        with self.assertRaises(RuntimeError):
            self.branch.amend_and_push(BRANCH, self.head, "CHANGELOG.md", "rewritten\n")
        self.assertEqual(git(self.remote, "log", "-1", BRANCH, "--format=%s"), "newer")
