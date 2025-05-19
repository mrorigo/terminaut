#!/usr/bin/env uv run
# /// script
# dependencies = [
#   "openai>=1.3.0",
#   "colorama",
#   "pyyaml"
# ]
# ///
import unittest
from unittest.mock import patch, MagicMock

from terminaut.cli import process_input_for_manual_rules
from terminaut.rules import ProjectRule, RuleType

class TestProcessInputForManualRules(unittest.TestCase):
    def setUp(self):
        self.mock_rule_manager = MagicMock()

        # Setup test rules
        self.rule_a = ProjectRule(
            name="RuleA",
            path="/path/to/RuleA.mdc",
            rule_type=RuleType.MANUAL,
            raw_content="RuleA content"
        )

        self.rule_b = ProjectRule(
            name="RuleB",
            path="/path/to/RuleB.mdc",
            rule_type=RuleType.MANUAL,
            raw_content="RuleB content"
        )

        # Setup mock get_manual_rule to return test rules
        def mock_get_manual_rule(name):
            if name == "RuleA":
                return self.rule_a
            elif name == "RuleB":
                return self.rule_b
            return None

        self.mock_rule_manager.get_manual_rule.side_effect = mock_get_manual_rule

        # Setup mock resolve_rule_content
        self.mock_rule_manager.resolve_rule_content.side_effect = lambda rule: f"Resolved {rule.name} content"

    def test_valid_rule_mention(self):
        """Test processing input with a valid rule mention."""
        with patch("terminaut.cli.output") as mock_output:
            messages, processed_text = process_input_for_manual_rules(
                "Hello, please use @RuleA for this task",
                self.mock_rule_manager
            )

            # Verify rule was looked up
            self.mock_rule_manager.get_manual_rule.assert_called_with("RuleA")

            # Verify message list contains one system message
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "system")
            self.assertIn("Manually Invoked Project Rule: RuleA", messages[0]["content"])
            self.assertIn("Resolved RuleA content", messages[0]["content"])

            # Verify no warnings were logged
            mock_output.assert_not_called()

            # Verify text is unchanged
            self.assertEqual(processed_text, "Hello, please use @RuleA for this task")

    def test_invalid_rule_mention(self):
        """Test processing input with an invalid rule mention."""
        with patch("terminaut.cli.output") as mock_output:
            messages, processed_text = process_input_for_manual_rules(
                "Hello, please use @InvalidRule for this task",
                self.mock_rule_manager
            )

            # Verify rule was looked up
            self.mock_rule_manager.get_manual_rule.assert_called_with("InvalidRule")

            # Verify empty message list
            self.assertEqual(len(messages), 0)

            # Verify warning was logged
            mock_output.assert_called_once()
            args, kwargs = mock_output.call_args
            self.assertEqual(args[0], "warning")
            self.assertIn("InvalidRule not found", args[1])

            # Verify text is unchanged
            self.assertEqual(processed_text, "Hello, please use @InvalidRule for this task")

    def test_multiple_rule_mentions(self):
        """Test processing input with multiple valid rule mentions."""
        with patch("terminaut.cli.output") as mock_output:
            messages, processed_text = process_input_for_manual_rules(
                "Use both @RuleA and @RuleB together",
                self.mock_rule_manager
            )

            # Verify both rules were looked up
            self.assertEqual(self.mock_rule_manager.get_manual_rule.call_count, 2)

            # Verify message list contains two system messages
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["role"], "system")
            self.assertEqual(messages[1]["role"], "system")
            self.assertIn("RuleA", messages[0]["content"])
            self.assertIn("RuleB", messages[1]["content"])

            # Verify no warnings were logged
            mock_output.assert_not_called()

            # Verify text is unchanged
            self.assertEqual(processed_text, "Use both @RuleA and @RuleB together")

    def test_mixed_valid_invalid_mentions(self):
        """Test processing input with both valid and invalid rule mentions."""
        with patch("terminaut.cli.output") as mock_output:
            messages, processed_text = process_input_for_manual_rules(
                "Use @RuleA but not @InvalidRule",
                self.mock_rule_manager
            )

            # Verify both rules were looked up
            self.assertEqual(self.mock_rule_manager.get_manual_rule.call_count, 2)

            # Verify message list contains one system message (for valid rule)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "system")
            self.assertIn("RuleA", messages[0]["content"])

            # Verify warning was logged for invalid rule
            mock_output.assert_called_once()
            args, kwargs = mock_output.call_args
            self.assertEqual(args[0], "warning")
            self.assertIn("InvalidRule not found", args[1])

            # Verify text is unchanged
            self.assertEqual(processed_text, "Use @RuleA but not @InvalidRule")

    def test_no_rule_mentions(self):
        """Test processing input without any rule mentions."""
        messages, processed_text = process_input_for_manual_rules(
            "Just a normal message without rules",
            self.mock_rule_manager
        )

        # Verify no rules were looked up
        self.mock_rule_manager.get_manual_rule.assert_not_called()

        # Verify empty message list
        self.assertEqual(len(messages), 0)

        # Verify text is unchanged
        self.assertEqual(processed_text, "Just a normal message without rules")

    def test_resolve_rule_content_called(self):
        """Test that rule content is resolved for found rules."""
        process_input_for_manual_rules(
            "Hello, please use @RuleA for this task",
            self.mock_rule_manager
        )

        # Verify resolve_rule_content was called for the found rule
        self.mock_rule_manager.resolve_rule_content.assert_called_once_with(self.rule_a)

    def test_null_rule_manager(self):
        """Test handling when rule_manager is None."""
        messages, processed_text = process_input_for_manual_rules(
            "Hello, please use @RuleA for this task",
            None
        )

        # Verify empty message list
        self.assertEqual(len(messages), 0)

        # Verify text is unchanged
        self.assertEqual(processed_text, "Hello, please use @RuleA for this task")

if __name__ == "__main__":
    unittest.main()
