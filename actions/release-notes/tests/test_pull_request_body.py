import unittest

from release_notes.errors import NotEligibleError
from release_notes.pull_request_body import ReleasePullRequestBody

HEADING = "## [1.9.1](https://github.com/owner/repo/compare/v1.9.0...v1.9.1) (2026-10-26)"
BODY = f""":robot: I have created a release *beep* *boop*
---


{HEADING}


### Miscellaneous Chores

* something ([93b626f](https://github.com/owner/repo/commit/93b626f))

---
This PR was generated with [Release Please](https://github.com/googleapis/release-please)."""


class ReleasePullRequestBodyTest(unittest.TestCase):
    def test_reads_the_heading_and_the_previous_tag(self):
        body = ReleasePullRequestBody.parse(BODY)
        self.assertEqual(body.heading, HEADING)
        self.assertEqual(body.previous_tag, "v1.9.0")

    def test_replaces_only_the_notes(self):
        rewritten = ReleasePullRequestBody.parse(BODY).with_notes(f"{HEADING}\n\n- New text")
        self.assertIn("- New text", rewritten)
        self.assertNotIn("Miscellaneous Chores", rewritten)
        self.assertTrue(rewritten.startswith(":robot:"))
        self.assertTrue(rewritten.endswith("(https://github.com/googleapis/release-please)."))

    def test_rewriting_is_parsed_back_to_the_same_heading(self):
        rewritten = ReleasePullRequestBody.parse(BODY).with_notes(f"{HEADING}\n\n- New text")
        self.assertEqual(ReleasePullRequestBody.parse(rewritten).heading, HEADING)

    def test_refuses_several_packages(self):
        with self.assertRaises(NotEligibleError):
            ReleasePullRequestBody.parse("header\n---\n<details><summary>a: 1.0.0</summary></details>\n---\nfooter")

    def test_refuses_a_body_without_delimiters(self):
        with self.assertRaises(NotEligibleError):
            ReleasePullRequestBody.parse("edited by hand")

    def test_the_first_release_has_no_previous_tag(self):
        body = ReleasePullRequestBody.parse("header\n---\n\n## 1.0.0 (2026-01-01)\n\n---\nfooter")
        with self.assertRaises(NotEligibleError):
            _ = body.previous_tag
