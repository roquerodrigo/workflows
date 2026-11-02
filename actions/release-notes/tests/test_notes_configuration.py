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
