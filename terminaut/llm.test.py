#!/usr/bin/env uv run
# /// script
# dependencies = [
#   "openai>=1.3.0",
#   "pytest",
# ]
# ///
import unittest
from unittest.mock import patch, MagicMock
import os

from terminaut.llm import LLM

class DummyRuleManager:
    def get_agent_rules_info(self): return []
    def get_applicable_rules(self, files): return []
    def get_manual_rule(self, name): return None
    def resolve_rule_content(self, rule): return ""

class TestExtractToolCallsFromText(unittest.TestCase):
    def setUp(self):
        # Patch openai.OpenAI to avoid real API calls
        patcher = patch("openai.OpenAI", autospec=True)
        self.addCleanup(patcher.stop)
        patcher.start()
        os.environ["OPENAI_API_KEY"] = "dummy"
        self.llm = LLM(model="dummy", rule_manager=DummyRuleManager())

    def test_basic_apply_patch_detection(self):
        text = (
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch\n"
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "bash")
        self.assertIn("apply_patch", calls[0]["arguments"]["command"])
        self.assertIn("*** Begin Patch", calls[0]["arguments"]["command"])
        self.assertIn("*** End Patch", calls[0]["arguments"]["command"])

    def test_apply_patch_no_trailing_newline(self):
        text = (
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch"
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 1)
        self.assertIn("*** End Patch", calls[0]["arguments"]["command"])

    def test_apply_patch_with_surrounding_text(self):
        text = (
            "Here is your patch:\n"
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch\n"
            "Let me know if you need more."
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "bash")

    def test_apply_patch_multiple_patches(self):
        text = (
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch\n"
            "Some text\n"
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: bar.txt\n"
            "world\n"
            "*** End Patch\n"
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call["name"] == "bash" for call in calls))
        self.assertIn("foo.txt", calls[0]["arguments"]["command"])
        self.assertIn("bar.txt", calls[1]["arguments"]["command"])

    def test_apply_patch_patch_at_end_of_text(self):
        text = (
            "Some intro text\n"
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch"
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 1)
        self.assertIn("foo.txt", calls[0]["arguments"]["command"])

    def test_apply_patch_patch_only(self):
        text = (
            "apply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch"
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 1)
        self.assertIn("foo.txt", calls[0]["arguments"]["command"])

    def test_apply_patch_with_extra_newlines(self):
        text = (
            "\n\napply_patch\n"
            "*** Begin Patch\n"
            "*** create: foo.txt\n"
            "hello\n"
            "*** End Patch\n\n"
        )
        calls = self.llm.extract_tool_calls_from_text(text)
        self.assertEqual(len(calls), 1)
        self.assertIn("foo.txt", calls[0]["arguments"]["command"])

if __name__ == "__main__":
    unittest.main()
