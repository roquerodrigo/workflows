import unittest

from release_notes.errors import RejectedNotesError
from release_notes.notes_configuration import DEFAULT_SECTION_TITLES, Changelog, NotesConfiguration
from release_notes.notes_writer import no_notes
from release_notes.release_notes import ReleaseNotes, published_notes
from release_notes.release_source import ReleaseSource

TWO_LANGUAGES = """
[[changelogs]]
language = "pt-BR"

[[changelogs]]
language = "en"
path = "docs/CHANGELOG.en.md"
release_path = "docs/releases/en/{version}.md"
"""


def changelog_in(language):
    return Changelog.of({"language": language})


def entry(category="fixed", text="Text.", pull_requests=()):
    return {"category": category, "text": text, "pull_requests": list(pull_requests)}


def validated(
    *entries,
    summary="",
    title="",
    known=frozenset(),
    breaking=False,
    titles=DEFAULT_SECTION_TITLES["en"],
    requires_title=False,
    bold_entries=False,
):
    return ReleaseNotes.validated(
        {"title": title, "summary": summary, "entries": list(entries)},
        set(known),
        has_breaking_commit=breaking,
        section_titles=titles,
        requires_title=requires_title,
        bold_entries=bold_entries,
    )


class ValidationTest(unittest.TestCase):
    def test_drops_a_pull_request_number_outside_the_release(self):
        notes = validated(entry(pull_requests=[1, 99]), known={1})
        self.assertEqual(notes.entries[0].pull_requests, (1,))

    def test_collapses_lines_so_a_text_cannot_add_a_delimiter(self):
        self.assertEqual(validated(entry(text="One\n---\ntwo")).entries[0].text, "One --- two")

    def test_rejects_markup_that_could_mislead_a_reader(self):
        for text in ("See https://evil.example", "![x](y)", "[x](y)", "<details>", "</summary>", "thanks @someone"):
            with self.subTest(text=text), self.assertRaises(RejectedNotesError):
                validated(entry(text=text))

    def test_keeps_an_address_that_is_not_a_mention(self):
        self.assertEqual(validated(entry(text="Uses user@example.com.")).entries[0].text, "Uses user@example.com.")

    def test_rejects_a_summary_with_a_link(self):
        with self.assertRaises(RejectedNotesError):
            validated(entry(), summary="See https://evil.example")

    def test_rejects_a_breaking_commit_without_a_breaking_entry(self):
        with self.assertRaises(RejectedNotesError):
            validated(entry(), breaking=True)

    def test_rejects_an_empty_entry(self):
        with self.assertRaises(RejectedNotesError):
            validated(entry(text="   "))

    def test_rejects_a_section_the_project_does_not_have(self):
        with self.assertRaises(RejectedNotesError):
            validated(entry("fixed"), titles={"balance": "Balance"})

    def test_rejects_a_release_with_entries_and_no_title_when_the_project_asks_for_one(self):
        with self.assertRaises(RejectedNotesError):
            validated(entry(), requires_title=True)

    def test_a_release_without_entries_needs_no_title(self):
        self.assertEqual(validated(requires_title=True).title, "")

    def test_rejects_a_title_with_a_link_or_bold_of_its_own(self):
        for title in ("See https://evil.example", "Two **words**"):
            with self.subTest(title=title), self.assertRaises(RejectedNotesError):
                validated(entry(), title=title)

    def test_rejects_an_entry_that_leaves_its_bold_open(self):
        with self.assertRaises(RejectedNotesError):
            validated(entry(text="**Open."), bold_entries=True)

    def test_keeps_closed_bold_in_an_entry(self):
        self.assertEqual(
            validated(entry(text="**One** and **two**."), bold_entries=True).entries[0].text, "**One** and **two**."
        )

    def test_leaves_entries_alone_when_the_project_does_not_ask_for_bold(self):
        self.assertEqual(validated(entry(text="2 ** 3")).entries[0].text, "2 ** 3")


class RenderTest(unittest.TestCase):
    def test_the_title_goes_in_bold_above_the_text(self):
        notes = validated(entry(text="Fix."), title="A Quiet Day", summary="A tale.")
        self.assertEqual(
            notes.render(changelog_in("en"), "owner/repo"),
            "**A Quiet Day**\n\nA tale.\n\n### Bug fixes\n\n- Fix.\n",
        )

    def test_a_release_without_user_facing_changes_shows_no_title(self):
        self.assertEqual(
            validated(title="A Quiet Day").render(changelog_in("en"), "owner/repo"),
            "Internal maintenance only, with no changes for those who use the project.\n",
        )

    def test_groups_by_category_in_a_fixed_order(self):
        notes = validated(entry("fixed", "Fix."), entry("added", "Add.", [7]), known={7})
        self.assertEqual(
            notes.render(changelog_in("en"), "owner/repo"),
            "### New features\n\n- Add. ([#7](https://github.com/owner/repo/pull/7))\n\n### Bug fixes\n\n- Fix.\n",
        )

    def test_titles_follow_the_language(self):
        titles = DEFAULT_SECTION_TITLES["pt-BR"]
        self.assertIn("### Correções", validated(entry(), titles=titles).render(changelog_in("pt-BR"), "owner/repo"))

    def test_sections_follow_the_order_and_titles_of_the_project(self):
        titles = {"balance": "Balance", "fixes": "Bug fixes"}
        changelog = Changelog.of({"language": "en", "sections": titles})
        notes = validated(entry("fixes", "Fix."), entry("balance", "Tune."), summary="A tale.", titles=titles)
        self.assertEqual(
            notes.render(changelog, "owner/repo"),
            "A tale.\n\n### Balance\n\n- Tune.\n\n### Bug fixes\n\n- Fix.\n",
        )

    def test_a_release_without_user_facing_changes_says_so(self):
        rendered = validated().render(changelog_in("pt-BR"), "owner/repo")
        self.assertEqual(rendered, "Apenas manutenção interna, sem mudanças para quem usa o projeto.\n")


class SupportSectionTest(unittest.TestCase):
    def test_links_to_the_sponsors_page_of_the_owner(self):
        self.assertIn("(https://github.com/sponsors/owner)", changelog_in("en").support_section("owner/repo"))

    def test_follows_the_language(self):
        self.assertTrue(changelog_in("en").support_section("owner/repo").startswith("### Support\n"))
        self.assertTrue(changelog_in("pt-BR").support_section("owner/repo").startswith("### Apoio\n"))


class PublishedNotesTest(unittest.TestCase):
    def source(self, commits=()):
        configuration = NotesConfiguration.of(TWO_LANGUAGES, "en")
        return ReleaseSource("owner/repo", "digest", configuration, list(commits))

    def test_writes_each_changelog_in_its_language_with_the_support_of_the_first(self):
        written = {
            "summary": {"pt-BR": "", "en": ""},
            "entries": [{"category": "fixed", "text": {"pt-BR": "Corrige.", "en": "Fixes."}, "pull_requests": []}],
        }
        self.assertEqual(
            published_notes(written, self.source()),
            {
                "digest": "digest",
                "support": changelog_in("pt-BR").support_section("owner/repo"),
                "changelogs": [
                    {"language": "pt-BR", "path": "", "release_path": "", "notes": "### Correções\n\n- Corrige.\n"},
                    {
                        "language": "en",
                        "path": "docs/CHANGELOG.en.md",
                        "release_path": "docs/releases/en/{version}.md",
                        "notes": "### Bug fixes\n\n- Fixes.\n",
                    },
                ],
            },
        )

    def test_writes_the_title_of_each_language(self):
        configuration = NotesConfiguration.of(f"title = true\n{TWO_LANGUAGES}", "en")
        written = {
            "title": {"pt-BR": "Dia Calmo", "en": "A Quiet Day"},
            "summary": {"pt-BR": "", "en": ""},
            "entries": [{"category": "fixed", "text": {"pt-BR": "Corrige.", "en": "Fixes."}, "pull_requests": []}],
        }
        changelogs = published_notes(written, ReleaseSource("owner/repo", "digest", configuration, []))["changelogs"]
        self.assertTrue(changelogs[0]["notes"].startswith("**Dia Calmo**\n\n"))
        self.assertTrue(changelogs[1]["notes"].startswith("**A Quiet Day**\n\n"))

    def test_rejects_a_missing_title_in_a_translation(self):
        configuration = NotesConfiguration.of(f"title = true\n{TWO_LANGUAGES}", "en")
        written = {
            "title": {"pt-BR": "Dia Calmo", "en": " "},
            "summary": {"pt-BR": "", "en": ""},
            "entries": [{"category": "fixed", "text": {"pt-BR": "Corrige.", "en": "Fixes."}, "pull_requests": []}],
        }
        with self.assertRaises(RejectedNotesError):
            published_notes(written, ReleaseSource("owner/repo", "digest", configuration, []))

    def test_a_release_without_commits_needs_no_title(self):
        configuration = NotesConfiguration.of(f"title = true\n{TWO_LANGUAGES}", "en")
        source = ReleaseSource("owner/repo", "digest", configuration, [])
        notes = published_notes(no_notes(source), source)["changelogs"][0]["notes"]
        self.assertEqual(notes, "Apenas manutenção interna, sem mudanças para quem usa o projeto.\n")

    def test_rejects_markup_in_a_translation(self):
        written = {
            "summary": {"pt-BR": "", "en": ""},
            "entries": [
                {
                    "category": "fixed",
                    "text": {"pt-BR": "Corrige.", "en": "See https://evil.example"},
                    "pull_requests": [],
                }
            ],
        }
        with self.assertRaises(RejectedNotesError):
            published_notes(written, self.source())
