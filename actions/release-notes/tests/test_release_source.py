import json
import unittest

from release_notes.conventional_commit import ConventionalCommit, visible_types
from release_notes.errors import NotEligibleError, NotesUnchangedError
from release_notes.release_source import ReleaseSource, ReleaseSourceCollector, language_of

CONFIGURATION = {
    "include-component-in-tag": False,
    "packages": {
        ".": {
            "changelog-sections": [
                {"type": "feat", "section": "Features"},
                {"type": "deps-dev", "section": "Development", "hidden": True},
            ]
        }
    },
}
NOTES = 'prompt = "Be brief."\npriority_paths = ["data/"]\n[sections]\nbalance = "Balance"\n'


class FakeGitHub:
    def __init__(self, *, configuration=CONFIGURATION, notes=None, files=None, pull_requests=(), tag_exists=True):
        self._configuration = configuration
        self._notes = notes
        self._files = files
        self._pull_requests = list(pull_requests)
        self._tag_exists = tag_exists

    def get_or_none(self, path):
        assert path == "repos/o/r/git/ref/tags/v1.0.0"
        return {"ref": "refs/tags/v1.0.0"} if self._tag_exists else None

    def get(self, path):
        if path == "repos/o/r":
            return {"default_branch": "main"}
        if path == "repos/o/r/commits/main":
            return {"sha": "released"}
        if path == "repos/o/r/commits/v1.1.0":
            return {"parents": [{"sha": "released"}]}
        if path == "repos/o/r/pulls?state=open&per_page=100":
            return self._pull_requests
        if path == "repos/o/r/commits/human":
            return {
                "author": {"login": "someone"},
                "commit": {"message": "feat: add a thing"},
                "files": self._files
                or [
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
        if path == ".release-please-manifest.json":
            return json.dumps({".": "1.0.0"})
        if path == "hacs.json":
            return json.dumps({"country": ["BR"]})
        if path == ".github/release-notes.toml":
            return self._notes
        raise AssertionError(path)

    def compared_commits(self, repository, base, head):
        assert (base, head) == ("v1.0.0", "released")
        return [
            {"sha": "human", "commit": {"message": "feat: add a thing"}},
            {"sha": "hidden", "commit": {"message": "deps-dev(deps-dev): bump ruff"}},
            {"sha": "other", "commit": {"message": "not conventional"}},
            {"sha": "bot", "commit": {"message": "feat!: bot change"}},
        ]


def collector(github):
    return ReleaseSourceCollector(github, "o/r", "release-please-config.json", ".release-please-manifest.json")


def collect(github):
    return collector(github).collect()


def release_pull_request(body):
    return {"number": 5, "title": "chore", "body": body, "head": {"ref": "release-please--branches--main"}}


class CollectorTest(unittest.TestCase):
    def test_keeps_only_the_commits_the_project_shows(self):
        source = collect(FakeGitHub())
        self.assertEqual([commit.pull_request_number for commit in source.commits], [12, 13])
        self.assertEqual(source.notes_configuration.language, "pt-BR")
        self.assertTrue(source.has_breaking_commit)

    def test_omits_generated_files_and_everything_a_bot_wrote(self):
        human, bot = collect(FakeGitHub()).commits
        self.assertEqual([file.patch for file in human.files], ["+code", ""])
        self.assertEqual(human.pull_request_description, "Details")
        self.assertEqual(bot.pull_request_description, "")
        self.assertEqual(bot.files[0].patch, "")

    def test_a_first_release_has_no_tag_to_compare_with(self):
        with self.assertRaises(NotEligibleError):
            collect(FakeGitHub(tag_exists=False))

    def test_refuses_tags_that_carry_a_component(self):
        with self.assertRaises(NotEligibleError):
            collect(FakeGitHub(configuration={"packages": {".": {}}}))

    def test_stops_when_the_open_pull_request_carries_the_notes_of_these_commits(self):
        digest = collect(FakeGitHub()).digest
        pull_request = release_pull_request(f"---\nNotes\n---\n<!-- release-notes: {digest} -->")
        with self.assertRaises(NotesUnchangedError) as raised:
            collect(FakeGitHub(pull_requests=[pull_request]))
        self.assertEqual(raised.exception.pull_request, pull_request)

    def test_writes_again_when_the_open_pull_request_has_other_notes(self):
        for body in (f"<!-- release-notes: {'0' * 64} -->", "---\nDefault text\n---", None):
            with self.subTest(body=body):
                collect(FakeGitHub(pull_requests=[release_pull_request(body)]))

    def test_a_change_to_the_notes_configuration_writes_the_notes_again(self):
        self.assertNotEqual(collect(FakeGitHub()).digest, collect(FakeGitHub(notes=NOTES)).digest)

    def test_a_past_release_leaves_its_release_commit_out(self):
        source = collector(FakeGitHub()).collect_past_release("v1.0.0", "v1.1.0")
        self.assertEqual([commit.pull_request_number for commit in source.commits], [12, 13])

    def test_refuses_several_packages(self):
        with self.assertRaises(NotEligibleError):
            collect(FakeGitHub(configuration={"packages": {"a": {}, "b": {}}}))

    def test_survives_the_trip_through_json(self):
        source = collect(FakeGitHub(notes=NOTES))
        self.assertEqual(ReleaseSource.from_json(source.to_json()), source)

    def test_keeps_the_defaults_without_a_notes_configuration(self):
        configuration = collect(FakeGitHub()).notes_configuration
        self.assertEqual(configuration.prompt, "")
        self.assertEqual(configuration.section_titles["fixed"], "Correções")

    def test_reads_the_notes_configuration_of_the_project(self):
        configuration = collect(FakeGitHub(notes=NOTES)).notes_configuration
        self.assertEqual(configuration.prompt, "Be brief.")
        self.assertEqual(list(configuration.section_titles), ["breaking", "balance"])

    def test_a_declared_language_decides_the_language_of_the_release(self):
        source = collect(FakeGitHub(notes='language = "en"'))
        self.assertEqual(source.notes_configuration.language, "en")
        self.assertEqual(source.notes_configuration.section_titles["fixed"], "Bug fixes")

    def test_reads_priority_files_first_and_in_full(self):
        long_patch = "+" + "x" * 30_000
        files = [
            {"filename": f"assets/{index}.json", "additions": 1, "deletions": 0, "patch": long_patch}
            for index in range(6)
        ] + [{"filename": "data/unit.json", "additions": 1, "deletions": 1, "patch": long_patch}]
        human, _ = collect(FakeGitHub(notes=NOTES, files=files)).commits
        self.assertEqual(human.files[0].path, "data/unit.json")
        self.assertEqual(human.files[0].patch, long_patch)
        self.assertEqual(sum(len(file.patch) for file in human.files[1:]), 20_000)

    def test_a_bot_patch_stays_out_even_in_a_priority_file(self):
        notes = 'priority_paths = ["code.py"]'
        _, bot = collect(FakeGitHub(notes=notes)).commits
        self.assertEqual(bot.files[0].patch, "")


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
