#!/usr/bin/env uv run
# /// script
# dependencies = [
#   "openai>=1.3.0",
#   "colorama",
#   "pyyaml"
# ]
# ///
import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock

from rules import RuleType, ProjectRule
from llm import LLM

class TestLLMRuleIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = self.temp_dir.name

        # Create a referenced file for testing @file resolution
        self.ref_file_path = os.path.join(self.project_root, "reference.txt")
        with open(self.ref_file_path, "w") as f:
            f.write("Referenced file content")

        # Set up mock rule manager with ALWAYS and AUTO_ATTACHED rules
        self.rule_manager = MagicMock()

        # Create the mock rules
        self.always_rule = ProjectRule(
            name="always_rule",
            path=os.path.join(self.project_root, "always.mdc"),
            rule_type=RuleType.ALWAYS,
            raw_content="Always rule content with @reference.txt",
            description="An always-applied rule",
            referenced_files=["reference.txt"]
        )

        self.auto_rule = ProjectRule(
            name="auto_rule",
            path=os.path.join(self.project_root, "auto.mdc"),
            rule_type=RuleType.AUTO_ATTACHED,
            raw_content="Auto-attached rule for Python files",
            description="A Python file rule",
            globs=["*.py"],
            referenced_files=[]
        )

        # Set up rule_manager mock methods
        self.rule_manager.get_agent_rules_info.return_value = [
            ("always_rule", "An always-applied rule"),
            ("auto_rule", "A Python file rule")
        ]

        # Mock resolve_rule_content to simulate @file resolution
        def mock_resolve_rule_content(rule):
            if rule == self.always_rule:
                return rule.raw_content.replace("@reference.txt", "Referenced file content")
            return rule.raw_content

        self.rule_manager.resolve_rule_content.side_effect = mock_resolve_rule_content

        # Setup base system prompt for LLM
        self.base_system_prompt = "You are a helpful AI assistant."

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch('llm.LLM._non_stream_response')
    def test_always_rule(self, mock_non_stream):
        # Mock the _non_stream_response method to avoid actual OpenAI call
        # Just return empty string and empty tool calls
        mock_non_stream.return_value = ("", [])

        # Configure get_applicable_rules to return only the ALWAYS rule
        self.rule_manager.get_applicable_rules.return_value = [self.always_rule]

        # Instantiate LLM with mocked rule_manager
        llm = LLM(
            model="gpt-4",
            system_prompt=self.base_system_prompt,
            rule_manager=self.rule_manager
        )

        # Call LLM with a user message that doesn't mention any files
        llm([{"role": "user", "content": "hello"}], stream=False)

        # Extract the messages that were passed to _non_stream_response
        call_args = mock_non_stream.call_args
        self.assertIsNotNone(call_args)
        messages = call_args[0][0]  # First argument to the mocked method

        # Verify structure: system prompt (with ALWAYS rule) + user message
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "hello")

        # Verify system prompt contains resolved ALWAYS rule content
        system_content = messages[0]["content"]
        self.assertIn("You are a helpful AI assistant", system_content)
        self.assertIn("Applied Project Rule: always_rule", system_content)
        self.assertIn("Referenced file content", system_content)
        self.assertNotIn("@reference.txt", system_content)

        # Verify agent rules info section is included
        self.assertIn("The following project rules are available", system_content)
        self.assertIn("- always_rule: An always-applied rule", system_content)
        self.assertIn("- auto_rule: A Python file rule", system_content)

    @patch('llm.LLM._non_stream_response')
    def test_auto_attached_rule_triggered(self, mock_non_stream):
        # Mock the _non_stream_response method to avoid actual OpenAI call
        mock_non_stream.return_value = ("", [])

        # Configure get_applicable_rules to return both rules when .py file is mentioned
        def mock_get_applicable(active_files):
            if any(".py" in file for file in active_files):
                return [self.always_rule, self.auto_rule]
            return [self.always_rule]

        self.rule_manager.get_applicable_rules.side_effect = mock_get_applicable

        # Instantiate LLM with mocked rule_manager
        llm = LLM(
            model="gpt-4",
            system_prompt=self.base_system_prompt,
            rule_manager=self.rule_manager
        )

        # Call LLM with a user message that mentions a Python file
        llm([{"role": "user", "content": "look at main.py"}], stream=False)

        # Extract the messages that were passed to _non_stream_response
        call_args = mock_non_stream.call_args
        self.assertIsNotNone(call_args)
        messages = call_args[0][0]  # First argument to the mocked method

        # Verify structure: system prompt (with both rules) + user message
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "look at main.py")

        # Verify system prompt contains both rule contents
        system_content = messages[0]["content"]
        self.assertIn("Applied Project Rule: always_rule", system_content)
        self.assertIn("Referenced file content", system_content)
        self.assertIn("Applied Project Rule: auto_rule", system_content)
        self.assertIn("Auto-attached rule for Python files", system_content)

    @patch('llm.LLM._non_stream_response')
    def test_auto_attached_rule_not_triggered(self, mock_non_stream):
        # Mock the _non_stream_response method to avoid actual OpenAI call
        mock_non_stream.return_value = ("", [])

        # Configure get_applicable_rules to return only ALWAYS rule for non-.py files
        def mock_get_applicable(active_files):
            if any(".py" in file for file in active_files):
                return [self.always_rule, self.auto_rule]
            return [self.always_rule]

        self.rule_manager.get_applicable_rules.side_effect = mock_get_applicable

        # Instantiate LLM with mocked rule_manager
        llm = LLM(
            model="gpt-4",
            system_prompt=self.base_system_prompt,
            rule_manager=self.rule_manager
        )

        # Call LLM with a user message that mentions a text file, not a Python file
        llm([{"role": "user", "content": "look at main.txt"}], stream=False)

        # Extract the messages that were passed to _non_stream_response
        call_args = mock_non_stream.call_args
        self.assertIsNotNone(call_args)
        messages = call_args[0][0]  # First argument to the mocked method

        # Verify structure: system prompt (with ALWAYS rule only) + user message
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "look at main.txt")

        # Verify system prompt contains ALWAYS rule but not AUTO_ATTACHED rule
        system_content = messages[0]["content"]
        self.assertIn("Applied Project Rule: always_rule", system_content)
        self.assertIn("Referenced file content", system_content)
        self.assertNotIn("Applied Project Rule: auto_rule", system_content)
        self.assertNotIn("Auto-attached rule for Python files", system_content)

if __name__ == "__main__":
    unittest.main()
