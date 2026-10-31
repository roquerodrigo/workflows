import unittest

from release_notes.changelog import replace_section

HEADING = "## [1.1.0](https://github.com/owner/repo/compare/v1.0.0...v1.1.0) (2026-01-02)"
CHANGELOG = f"""# Changelog

{HEADING}


### Features

* old text

### [1.0.1](https://github.com/owner/repo/compare/v1.0.0...v1.0.1) (2026-01-01)

* older
"""


class ReplaceSectionTest(unittest.TestCase):
    def test_replaces_the_section_and_keeps_the_older_ones(self):
        updated = replace_section(CHANGELOG, HEADING, f"{HEADING}\n\n### Novidades\n\n- new text\n")
        self.assertIn("- new text", updated)
        self.assertNotIn("old text", updated)
        self.assertIn("* older", updated)
        self.assertTrue(updated.startswith("# Changelog\n\n"))

    def test_a_section_title_is_not_mistaken_for_the_next_version(self):
        updated = replace_section(CHANGELOG, HEADING, f"{HEADING}\n\n### Novidades\n\n- new text\n")
        self.assertEqual(replace_section(updated, HEADING, f"{HEADING}\n\n- again\n").count("Novidades"), 0)

    def test_replaces_the_only_section(self):
        updated = replace_section(f"# Changelog\n\n{HEADING}\n\n* old\n", HEADING, f"{HEADING}\n\n- new\n")
        self.assertEqual(updated, f"# Changelog\n\n{HEADING}\n\n- new\n")

    def test_reports_a_missing_section(self):
        self.assertIsNone(replace_section("# Changelog\n", HEADING, "text"))
