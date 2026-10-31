import unittest

from release_notes.errors import RejectedNotesError
from release_notes.release_notes import ReleaseNotes, support_section

HEADING = "## [1.1.0](https://github.com/owner/repo/compare/v1.0.0...v1.1.0) (2026-01-02)"


def entry(category="fixed", text="Text.", pull_requests=()):
    return {"category": category, "text": text, "pull_requests": list(pull_requests)}


def validated(*entries, summary="", known=frozenset(), breaking=False):
    return ReleaseNotes.validated(
        {"summary": summary, "entries": list(entries)}, set(known), has_breaking_commit=breaking
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


class RenderTest(unittest.TestCase):
    def test_groups_by_category_in_a_fixed_order(self):
        notes = validated(entry("fixed", "Fix."), entry("added", "Add.", [7]), known={7})
        self.assertEqual(
            notes.render(HEADING, "en", "owner/repo"),
            f"{HEADING}\n\n### New features\n\n- Add. ([#7](https://github.com/owner/repo/pull/7))"
            "\n\n### Bug fixes\n\n- Fix.\n",
        )

    def test_titles_follow_the_language(self):
        self.assertIn("### Correções", validated(entry()).render(HEADING, "pt-BR", "owner/repo"))

    def test_a_release_without_user_facing_changes_says_so(self):
        rendered = validated().render(HEADING, "pt-BR", "owner/repo")
        self.assertEqual(rendered, f"{HEADING}\n\nApenas manutenção interna, sem mudanças para quem usa o projeto.\n")


class SupportSectionTest(unittest.TestCase):
    def test_links_to_the_sponsors_page_of_the_owner(self):
        self.assertIn("(https://github.com/sponsors/owner)", support_section("en", "owner/repo"))

    def test_follows_the_language(self):
        self.assertTrue(support_section("en", "owner/repo").startswith("### Support\n"))
        self.assertTrue(support_section("pt-BR", "owner/repo").startswith("### Apoio\n"))
