import unittest

from release_notes.errors import InvalidNotesConfigurationError
from release_notes.notes_configuration import DEFAULT_SECTION_TITLES, NotesConfiguration
from release_notes.notes_writer import DEFAULT_PROMPT, FIXED_RULES, output_schema, system_prompt

CONFIGURATION = """
prompt = '''
Write like a bard.
'''
priority_paths = ["src/data/", "messages.ts"]

[sections]
balance = "Balance"
fixes = "Bug fixes"
"""

TWO_LANGUAGES = """
[[changelogs]]
language = "pt-BR"
path = "notes/mudancas.md"

[[changelogs]]
language = "en"
path = "docs/CHANGELOG.en.md"
"""
SPANISH = """
[[changelogs]]
language = "en"

[[changelogs]]
language = "es"
path = "docs/CHANGELOG.es.md"
no_user_facing_changes = "Sin cambios."
support = "Apoya en {url}"

[changelogs.sections]
breaking = "Cambios incompatibles"
added = "Novedades"
changed = "Mejoras"
fixed = "Correcciones"
"""
SAME_RELEASE_FILES = """
[[changelogs]]
language = "en"
release_path = "a/{version}.md"

[[changelogs]]
language = "pt-BR"
release_path = "a/{version}.md"
"""
RELEASE_FILES = """
[[changelogs]]
language = "en"
release_path = "docs/releases/en/{version}.md"

[[changelogs]]
language = "pt-BR"
release_path = "docs/releases/pt-BR/{version}.md"
"""
DIFFERENT_SECTIONS = """
[[changelogs]]
language = "en"
[changelogs.sections]
news = "News"

[[changelogs]]
language = "pt-BR"
path = "a.md"
"""


class NotesConfigurationTest(unittest.TestCase):
    def test_without_a_file_keeps_the_defaults_of_the_language(self):
        configuration = NotesConfiguration.of(None, "pt-BR")
        self.assertEqual(configuration.section_titles, DEFAULT_SECTION_TITLES["pt-BR"])
        self.assertEqual(configuration.prompt, "")
        self.assertFalse(configuration.is_priority("src/data/unit.json"))

    def test_reads_the_prompt_the_sections_in_order_and_the_paths(self):
        configuration = NotesConfiguration.of(CONFIGURATION, "en")
        self.assertEqual(configuration.prompt, "Write like a bard.")
        self.assertEqual(list(configuration.section_titles), ["breaking", "balance", "fixes"])
        self.assertTrue(configuration.is_priority("src/data/unit.json"))
        self.assertFalse(configuration.is_priority("src/game.ts"))

    def test_keeps_a_breaking_section_the_project_left_out_in_its_language(self):
        titles = NotesConfiguration.of(CONFIGURATION, "pt-BR").section_titles
        self.assertEqual(titles["breaking"], "Mudanças incompatíveis")

    def test_lets_the_project_name_the_breaking_section(self):
        titles = NotesConfiguration.of('[sections]\nnews = "News"\nbreaking = "Heads up"', "en").section_titles
        self.assertEqual(list(titles.items()), [("breaking", "Heads up"), ("news", "News")])

    def test_a_file_with_only_a_prompt_keeps_the_default_sections(self):
        configuration = NotesConfiguration.of('prompt = "Hello"', "en")
        self.assertEqual(configuration.section_titles, DEFAULT_SECTION_TITLES["en"])

    def test_keeps_the_language_of_the_project_without_a_declared_one(self):
        self.assertEqual(NotesConfiguration.of(None, "pt-BR").language, "pt-BR")
        self.assertEqual(NotesConfiguration.of('prompt = "Hello"', "en").language, "en")

    def test_a_declared_language_replaces_the_one_of_the_project(self):
        configuration = NotesConfiguration.of('language = "pt-BR"\n[sections]\nnews = "Novidades"', "en")
        self.assertEqual(configuration.language, "pt-BR")
        self.assertEqual(configuration.section_titles["breaking"], "Mudanças incompatíveis")

    def test_refuses_what_it_cannot_use(self):
        for text in (
            'language = "fr"',
            "language = 1",
            'promt = "typo"',
            "prompt = 1",
            'sections = "news"',
            '[sections]\nnews = ""',
            "[sections]\nnews = 1",
            'priority_paths = "src/"',
            'priority_paths = [""]',
        ):
            with self.subTest(text=text), self.assertRaises(InvalidNotesConfigurationError):
                NotesConfiguration.of(text, "en")


class ChangelogsTest(unittest.TestCase):
    def test_without_changelogs_the_only_file_stays_with_release_please(self):
        configuration = NotesConfiguration.of(None, "pt-BR")
        self.assertEqual([changelog.path for changelog in configuration.changelogs], [""])
        self.assertEqual(configuration.languages, ["pt-BR"])

    def test_the_first_changelog_is_the_language_of_the_release(self):
        configuration = NotesConfiguration.of(TWO_LANGUAGES, "en")
        self.assertEqual(configuration.language, "pt-BR")
        self.assertEqual(configuration.languages, ["pt-BR", "en"])
        self.assertEqual(configuration.primary.path, "notes/mudancas.md")
        self.assertEqual(configuration.changelogs[1].section_titles, DEFAULT_SECTION_TITLES["en"])

    def test_a_language_without_built_in_texts_declares_them(self):
        configuration = NotesConfiguration.of(SPANISH, "en")
        spanish = configuration.changelogs[1]
        self.assertEqual(spanish.section_titles["fixed"], "Correcciones")
        self.assertEqual(spanish.support_section("owner/repo"), "Apoya en https://github.com/sponsors/owner")

    def test_keeps_each_release_in_its_own_file(self):
        configuration = NotesConfiguration.of(RELEASE_FILES, "en")
        self.assertEqual(
            [changelog.release_path for changelog in configuration.changelogs],
            ["docs/releases/en/{version}.md", "docs/releases/pt-BR/{version}.md"],
        )

    def test_a_translation_can_live_only_in_the_files_of_its_releases(self):
        self.assertEqual(NotesConfiguration.of(RELEASE_FILES, "en").changelogs[1].path, "")

    def test_refuses_what_it_cannot_use(self):
        for text in (
            '[[changelogs]]\nlanguage = "en"\nrelease_path = "docs/release.md"',
            '[[changelogs]]\nlanguage = "en"\nrelease_path = "../{version}.md"',
            '[[changelogs]]\nlanguage = "en"\nrelease_path = 1',
            SAME_RELEASE_FILES,
            "changelogs = []",
            'changelogs = "en"',
            'language = "en"\n[[changelogs]]\nlanguage = "en"',
            '[[changelogs]]\nlanguage = "fr"',
            "[[changelogs]]\nlanguage = 1",
            '[[changelogs]]\nlanguage = "not a tag"',
            '[[changelogs]]\nlanguage = "en"\nlanguges = "pt-BR"',
            '[[changelogs]]\nlanguage = "en"\n[[changelogs]]\nlanguage = "pt-BR"',
            '[[changelogs]]\nlanguage = "en"\npath = "a.md"\n[[changelogs]]\nlanguage = "pt-BR"\npath = "a.md"',
            '[[changelogs]]\nlanguage = "en"\n[[changelogs]]\nlanguage = "en"\npath = "a.md"',
            '[[changelogs]]\nlanguage = "en"\npath = "../outside.md"',
            '[[changelogs]]\nlanguage = "en"\npath = "/etc/outside.md"',
            DIFFERENT_SECTIONS,
        ):
            with self.subTest(text=text), self.assertRaises(InvalidNotesConfigurationError):
                NotesConfiguration.of(text, "en")


class SystemPromptTest(unittest.TestCase):
    def test_uses_the_default_prompt_without_a_project_prompt(self):
        self.assertIn(DEFAULT_PROMPT, system_prompt(NotesConfiguration.of(None, "en")))

    def test_a_project_prompt_replaces_the_default_and_never_the_fixed_rules(self):
        prompt = system_prompt(NotesConfiguration.of(CONFIGURATION, "en"))
        self.assertIn("Write like a bard.", prompt)
        self.assertNotIn(DEFAULT_PROMPT, prompt)
        self.assertIn(FIXED_RULES, prompt)

    def test_tells_the_model_the_sections_it_can_use(self):
        configuration = NotesConfiguration.of(CONFIGURATION, "en")
        self.assertIn("- `balance`: Balance\n", system_prompt(configuration))
        category = output_schema(configuration)["properties"]["entries"]["items"]["properties"]["category"]
        self.assertEqual(category["enum"], ["breaking", "balance", "fixes"])

    def test_asks_for_each_text_in_every_language(self):
        schema = output_schema(NotesConfiguration.of(TWO_LANGUAGES, "en"))
        summary = schema["properties"]["summary"]
        self.assertEqual(summary["required"], ["pt-BR", "en"])
        self.assertEqual(schema["properties"]["entries"]["items"]["properties"]["text"], summary)
