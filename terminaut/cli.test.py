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
            rule_type=RuleType.MANUAL, # Or any type other than ALWAYS
            raw_content="RuleA content"
        )

        self.rule_b = ProjectRule(
            name="RuleB",
            path="/path/to/RuleB.mdc",
            rule_type=RuleType.AGENT_REQUESTED, # Or any type other than ALWAYS
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

    def test_valid_rule_mention(self):
        """Test processing input with a valid rule mention."""
        with patch("terminaut.cli.output") as mock_output:
            rule_names, processed_text = process_input_for_manual_rules(
                "Hello, please use @RuleA for this task",
                self.mock_rule_manager
            )

            # Verify rule was looked up
            self.mock_rule_manager.get_manual_rule.assert_called_with("RuleA")

            # Verify rule_names list contains the rule name
            self.assertEqual(len(rule_names), 1)
            self.assertIn("RuleA", rule_names)

            # Verify no warnings were logged
            mock_output.assert_not_called()

            # Verify text is unchanged
            self.assertEqual(processed_text, "Hello, please use @RuleA for this task")

    def test_invalid_rule_mention(self):
        """Test processing input with an invalid rule mention."""
        with patch("terminaut.cli.output") as mock_output:
            rule_names, processed_text = process_input_for_manual_rules(
                "Hello, please use @InvalidRule for this task",
                self.mock_rule_manager
            )

            # Verify rule was looked up
            self.mock_rule_manager.get_manual_rule.assert_called_with("InvalidRule")

            # Verify empty rule_names list
            self.assertEqual(len(rule_names), 0)

            # Verify warning was logged
            mock_output.assert_called_once()
            args, kwargs = mock_output.call_args
            self.assertEqual(args[0], "warning")
            self.assertIn("Manual rule @InvalidRule not found", args[1]) # Message changed slightly in source

            # Verify text is unchanged
            self.assertEqual(processed_text, "Hello, please use @InvalidRule for this task")

    def test_multiple_rule_mentions(self):
        """Test processing input with multiple valid rule mentions."""
        with patch("terminaut.cli.output") as mock_output:
            rule_names, processed_text = process_input_for_manual_rules(
                "Use both @RuleA and @RuleB together",
                self.mock_rule_manager
            )

            # Verify both rules were looked up
            self.assertEqual(self.mock_rule_manager.get_manual_rule.call_count, 2)
            self.mock_rule_manager.get_manual_rule.assert_any_call("RuleA")
            self.mock_rule_manager.get_manual_rule.assert_any_call("RuleB")


            # Verify rule_names list contains both rule names
            self.assertEqual(len(rule_names), 2)
            self.assertIn("RuleA", rule_names)
            self.assertIn("RuleB", rule_names)

            # Verify no warnings were logged
            mock_output.assert_not_called()

            # Verify text is unchanged
            self.assertEqual(processed_text, "Use both @RuleA and @RuleB together")

    def test_mixed_valid_invalid_mentions(self):
        """Test processing input with both valid and invalid rule mentions."""
        with patch("terminaut.cli.output") as mock_output:
            rule_names, processed_text = process_input_for_manual_rules(
                "Use @RuleA but not @InvalidRule",
                self.mock_rule_manager
            )

            # Verify both rules were looked up
            self.assertEqual(self.mock_rule_manager.get_manual_rule.call_count, 2)
            self.mock_rule_manager.get_manual_rule.assert_any_call("RuleA")
            self.mock_rule_manager.get_manual_rule.assert_any_call("InvalidRule")

            # Verify rule_names list contains one rule name (for valid rule)
            self.assertEqual(len(rule_names), 1)
            self.assertIn("RuleA", rule_names)

            # Verify warning was logged for invalid rule
            mock_output.assert_called_once()
            args, kwargs = mock_output.call_args
            self.assertEqual(args[0], "warning")
            self.assertIn("Manual rule @InvalidRule not found", args[1])

            # Verify text is unchanged
            self.assertEqual(processed_text, "Use @RuleA but not @InvalidRule")

    def test_no_rule_mentions(self):
        """Test processing input without any rule mentions."""
        rule_names, processed_text = process_input_for_manual_rules(
            "Just a normal message without rules",
            self.mock_rule_manager
        )

        # Verify no rules were looked up
        self.mock_rule_manager.get_manual_rule.assert_not_called()

        # Verify empty rule_names list
        self.assertEqual(len(rule_names), 0)

        # Verify text is unchanged
        self.assertEqual(processed_text, "Just a normal message without rules")

    def test_null_rule_manager(self):
        """Test handling when rule_manager is None."""
        rule_names, processed_text = process_input_for_manual_rules(
            "Hello, please use @RuleA for this task",
            None
        )

        # Verify empty rule_names list
        self.assertEqual(len(rule_names), 0)

        # Verify text is unchanged
        self.assertEqual(processed_text, "Hello, please use @RuleA for this task")

if __name__ == "__main__":
    unittest.main()