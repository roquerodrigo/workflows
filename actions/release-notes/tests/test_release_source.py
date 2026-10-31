import json
import unittest

from release_notes.conventional_commit import ConventionalCommit, visible_types
from release_notes.errors import NotEligibleError
from release_notes.release_source import ReleaseSource, ReleaseSourceCollector, language_of

CONFIGURATION = {
    "packages": {
        ".": {
            "changelog-sections": [
                {"type": "feat", "section": "Features"},
                {"type": "deps-dev", "section": "Development", "hidden": True},
            ]
        }
    }
}
BODY = "header\n---\n\n## [1.1.0](https://github.com/o/r/compare/v1.0.0...v1.1.0) (2026-01-01)\n\n---\nfooter"


class FakeGitHub:
    def __init__(self, *, branch="release-please--branches--main", configuration=CONFIGURATION, body=BODY):
        self._branch = branch
        self._configuration = configuration
        self._body = body

    def get(self, path):
        if path == "repos/o/r/pulls/5":
            return {"head": {"ref": self._branch, "sha": "head"}, "body": self._body}
        if path == "repos/o/r/commits/head":
            return {"parents": [{"sha": "released"}]}
        if path == "repos/o/r/commits/human":
            return {
                "author": {"login": "someone"},
                "commit": {"message": "feat: add a thing"},
                "files": [
                    {"filename": "code.py", "additions": 1, "deletions": 0, "patch": "+code"},
                    {"filename": "uv.lock", "additions": 9, "deletions": 9, "patch": "+lock"},
                ],
            }
        if path == "repos/o/r/commits/bot":
            return {
                "author": {"login": "dependabot[bot]"},
                "commit": {"message": "feat!: bot change"},
                "files": [{"filename": "code.py", "additions": 1, "deletions": 0, "patch": "+code"}],
            }
        if path == "repos/o/r/commits/human/pulls":
            return [{"number": 12, "title": "Add a thing", "body": "Details", "merged_at": "2026-01-01"}]
        if path == "repos/o/r/commits/bot/pulls":
            return [{"number": 13, "title": "Bump", "body": "Long upstream notes", "merged_at": "2026-01-01"}]
        raise AssertionError(path)

    def file_text(self, repository, path, ref):
        if path == "release-please-config.json":
            return json.dumps(self._configuration)
        if path == "hacs.json":
            return json.dumps({"country": ["BR"]})
        raise AssertionError(path)

    def compared_commits(self, repository, base, head):
        assert (base, head) == ("v1.0.0", "released")
        return [
            {"sha": "human", "commit": {"message": "feat: add a thing"}},
            {"sha": "hidden", "commit": {"message": "deps-dev(deps-dev): bump ruff"}},
            {"sha": "other", "commit": {"message": "not conventional"}},
            {"sha": "bot", "commit": {"message": "feat!: bot change"}},
        ]


def collect(github):
    return ReleaseSourceCollector(github, "o/r", "release-please-config.json").collect(5)


class CollectorTest(unittest.TestCase):
    def test_keeps_only_the_commits_the_project_shows(self):
        source = collect(FakeGitHub())
        self.assertEqual([commit.pull_request_number for commit in source.commits], [12, 13])
        self.assertEqual(source.language, "pt-BR")
        self.assertTrue(source.has_breaking_commit)

    def test_omits_generated_files_and_everything_a_bot_wrote(self):
        human, bot = collect(FakeGitHub()).commits
        self.assertEqual([file.patch for file in human.files], ["+code", ""])
        self.assertEqual(human.pull_request_description, "Details")
        self.assertEqual(bot.pull_request_description, "")
        self.assertEqual(bot.files[0].patch, "")

    def test_refuses_a_branch_that_release_please_does_not_own(self):
        with self.assertRaises(NotEligibleError):
            collect(FakeGitHub(branch="feature"))

    def test_refuses_several_packages(self):
        with self.assertRaises(NotEligibleError):
            collect(FakeGitHub(configuration={"packages": {"a": {}, "b": {}}}))

    def test_survives_the_trip_through_json(self):
        source = collect(FakeGitHub())
        self.assertEqual(ReleaseSource.from_json(source.to_json()), source)


class LanguageTest(unittest.TestCase):
    def test_a_brazilian_project_writes_in_portuguese(self):
        self.assertEqual(language_of('{"country": ["BR"]}'), "pt-BR")
        self.assertEqual(language_of('{"country": "BR"}'), "pt-BR")

    def test_anything_else_writes_in_english(self):
        for manifest in (None, "{}", '{"country": ["BR", "US"]}', '{"country": ["DE"]}'):
            with self.subTest(manifest=manifest):
                self.assertEqual(language_of(manifest), "en")


class ConventionalCommitTest(unittest.TestCase):
    def test_reads_type_and_breaking_marks(self):
        self.assertEqual(ConventionalCommit.parse("fix(sensor): a"), ConventionalCommit("fix", False))
        self.assertEqual(ConventionalCommit.parse("feat!: a"), ConventionalCommit("feat", True))
        self.assertEqual(ConventionalCommit.parse("feat: a\n\nBREAKING CHANGE: b"), ConventionalCommit("feat", True))
        self.assertIsNone(ConventionalCommit.parse("no type here"))

    def test_without_sections_follows_the_release_please_defaults(self):
        self.assertEqual(visible_types({}, {}), {"feat", "fix", "perf", "revert"})
