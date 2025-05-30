import unittest
import tempfile
import os
from unittest.mock import patch

from terminaut.rules import MdcParser, RuleType, ProjectRule

class TestMdcParser(unittest.TestCase):
    def setUp(self):
        self.parser = MdcParser()

    def test_valid_frontmatter_and_content(self):
        content = "---\ndescription: Test rule\n---\nThis is the rule content.\nSecond line."
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "testrule")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.name, "testrule")
        self.assertEqual(rule.path, tf.name)
        self.assertEqual(rule.raw_content, "This is the rule content.\nSecond line.")
        self.assertEqual(rule.rule_type, RuleType.AGENT_REQUESTED)
        os.unlink(tf.name)

    def test_no_frontmatter(self):
        content = "This is the entire file content.\nNo frontmatter here."
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "nofront")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.raw_content, content)
        os.unlink(tf.name)

    def test_incomplete_frontmatter(self):
        content = "---\nThis is not closed frontmatter.\nStill part of content."
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "incomplete")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.raw_content, content)
        os.unlink(tf.name)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write("")
            tf.flush()
            rule = self.parser.parse(tf.name, "empty")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.raw_content, "")
        os.unlink(tf.name)

    def test_nonexistent_file(self):
        fake_path = "/tmp/does_not_exist_12345.mdc"
        with patch("rules.output") as mock_output:
            rule = self.parser.parse(fake_path, "missing")
            self.assertIsNone(rule)
            self.assertTrue(mock_output.called)
            args, kwargs = mock_output.call_args
            self.assertEqual(args[0], "error")
            self.assertIn("Rule file not found", args[1])

    def test_yaml_frontmatter_with_description_globs_alwaysapply_true(self):
        content = (
            "---\n"
            "description: Test rule\n"
            "globs:\n"
            "  - '*.py'\n"
            "  - 'src/*.js'\n"
            "alwaysApply: true\n"
            "---\n"
            "Rule content here."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "yamltrue")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.description, "Test rule")
        self.assertEqual(rule.globs, ["*.py", "src/*.js"])
        self.assertTrue(rule.always_apply)
        os.unlink(tf.name)

    def test_yaml_frontmatter_with_alwaysapply_false(self):
        content = (
            "---\n"
            "description: Another rule\n"
            "globs:\n"
            "  - '*.md'\n"
            "alwaysApply: false\n"
            "---\n"
            "Another rule content."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "yamlfalse")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.description, "Another rule")
        self.assertEqual(rule.globs, ["*.md"])
        self.assertFalse(rule.always_apply)
        os.unlink(tf.name)

    def test_yaml_frontmatter_with_only_description(self):
        content = (
            "---\n"
            "description: Only description\n"
            "---\n"
            "Content with only description."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "desc_only")
        self.assertIsInstance(rule, ProjectRule)
        self.assertEqual(rule.description, "Only description")
        self.assertEqual(rule.globs, [])
        self.assertFalse(rule.always_apply)
        os.unlink(tf.name)

    def test_yaml_frontmatter_with_only_globs(self):
        content = (
            "---\n"
            "globs:\n"
            "  - '*.json'\n"
            "---\n"
            "Content with only globs."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "globs_only")
        self.assertIsInstance(rule, ProjectRule)
        self.assertIsNone(rule.description)
        self.assertEqual(rule.globs, ["*.json"])
        self.assertFalse(rule.always_apply)
        os.unlink(tf.name)

    def test_yaml_frontmatter_malformed_yaml(self):
        content = (
            "---\n"
            "description: Bad YAML: [unclosed\n"
            "---\n"
            "Malformed YAML content."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            with patch("rules.output") as mock_output:
                rule = self.parser.parse(tf.name, "malformed")
                self.assertIsInstance(rule, ProjectRule)
                self.assertIsNone(rule.description)
                self.assertEqual(rule.globs, [])
                self.assertFalse(rule.always_apply)
                self.assertTrue(mock_output.called)
                args, kwargs = mock_output.call_args
                self.assertEqual(args[0], "error")
                self.assertIn("YAML parsing error", args[1])
        os.unlink(tf.name)

    def test_yaml_frontmatter_not_a_dict(self):
        content = (
            "---\n"
            "- just\n"
            "- a\n"
            "- list\n"
            "---\n"
            "YAML is a list, not a dict."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            with patch("rules.output") as mock_output:
                rule = self.parser.parse(tf.name, "notadict")
                self.assertIsInstance(rule, ProjectRule)
                self.assertIsNone(rule.description)
                self.assertEqual(rule.globs, [])
                self.assertFalse(rule.always_apply)
                self.assertTrue(mock_output.called)
                args, kwargs = mock_output.call_args
                self.assertEqual(args[0], "error")
                self.assertIn("Frontmatter YAML is not a dict", args[1])
        os.unlink(tf.name)

    def test_rule_type_always(self):
        content = (
            "---\n"
            "alwaysApply: true\n"
            "description: Should be ALWAYS\n"
            "---\n"
            "Content."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "always")
        self.assertEqual(rule.rule_type, RuleType.ALWAYS)
        os.unlink(tf.name)

    def test_rule_type_auto_attached(self):
        content = (
            "---\n"
            "globs:\n"
            "  - '*.py'\n"
            "description: Should be AUTO_ATTACHED\n"
            "alwaysApply: false\n"
            "---\n"
            "Content."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "auto")
        self.assertEqual(rule.rule_type, RuleType.AUTO_ATTACHED)
        os.unlink(tf.name)

    def test_rule_type_agent_requested(self):
        content = (
            "---\n"
            "description: Should be AGENT_REQUESTED\n"
            "alwaysApply: false\n"
            "---\n"
            "Content."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "agentreq")
        self.assertEqual(rule.rule_type, RuleType.AGENT_REQUESTED)
        os.unlink(tf.name)

    def test_rule_type_manual(self):
        content = (
            "---\n"
            "---\n"
            "No metadata at all."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "manual")
        self.assertEqual(rule.rule_type, RuleType.MANUAL)
        os.unlink(tf.name)

    def test_at_file_reference_single(self):
        content = (
            "---\n"
            "description: Single file ref\n"
            "---\n"
            "This rule uses @file.py in its content."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "singlefile")
        self.assertIn("file.py", rule.referenced_files)
        self.assertEqual(rule.referenced_files, ["file.py"])
        os.unlink(tf.name)

    def test_at_file_reference_multiple(self):
        content = (
            "---\n"
            "description: Multiple refs\n"
            "---\n"
            "See @file1.txt and @file2.json for details."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "multifile")
        self.assertIn("file1.txt", rule.referenced_files)
        self.assertIn("file2.json", rule.referenced_files)
        self.assertEqual(set(rule.referenced_files), {"file1.txt", "file2.json"})
        os.unlink(tf.name)

    def test_at_file_reference_duplicates(self):
        content = (
            "---\n"
            "description: Duplicates\n"
            "---\n"
            "Use @file.py and again @file.py for more info."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "dupes")
        # Duplicates are allowed as found
        self.assertEqual(rule.referenced_files.count("file.py"), 2)
        os.unlink(tf.name)

    def test_at_file_reference_none(self):
        content = (
            "---\n"
            "description: No refs\n"
            "---\n"
            "This rule has no file references."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "norefs")
        self.assertEqual(rule.referenced_files, [])
        os.unlink(tf.name)

    def test_at_file_reference_non_file_patterns(self):
        content = (
            "---\n"
            "description: Non-file patterns\n"
            "---\n"
            "Mention @user and email name@domain.com but only @file.txt is a file."
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".mdc") as tf:
            tf.write(content)
            tf.flush()
            rule = self.parser.parse(tf.name, "nonfile")
        self.assertIn("file.txt", rule.referenced_files)
        self.assertNotIn("user", rule.referenced_files)
        self.assertNotIn("domain.com", rule.referenced_files)
        os.unlink(tf.name)

class TestRuleManager(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = self.tempdir.name

    def tearDown(self):
        self.tempdir.cleanup()

    def make_rule_file(self, rel_path, content="---\ndescription: test\n---\ncontent"):
        abs_path = os.path.join(self.project_root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_path

    def test_load_rules_discovers_and_loads_rules(self):
        # Setup directory structure
        rule1 = self.make_rule_file(".cursor/rules/rule1.mdc")
        rule2 = self.make_rule_file("subdir/.cursor/rules/rule2.mdc")
        rule3 = self.make_rule_file(".cursor/rules/subdir_rules/rule3.mdc")
        # Not a rule file
        other = self.make_rule_file("another_dir/no_rules_here.txt", "not a rule")

        # Patch MdcParser.parse to return a dummy ProjectRule for .mdc files, None for others
        dummy_rule = ProjectRule(
            name="dummy", path="dummy", rule_type=RuleType.MANUAL, raw_content="dummy"
        )
        with patch("terminaut.rules.MdcParser.parse") as mock_parse:
            def side_effect(path, name):
                if path.endswith(".mdc"):
                    # Return a unique rule for each file
                    return ProjectRule(name=name, path=path, rule_type=RuleType.MANUAL, raw_content="dummy")
                return None
            mock_parse.side_effect = side_effect
            mdc_parser = MdcParser()
            manager = RuleManager(self.project_root, mdc_parser)
            manager.load_rules()
            # Should load rule1 and rule2 only (rule3 is in subdir_rules, not a direct rules dir)
            loaded_names = [r.name for r in manager.rules]
            self.assertIn("rule1", loaded_names)
            self.assertIn("rule2", loaded_names)
            self.assertNotIn("rule3", loaded_names)
            self.assertEqual(len(manager.rules), 2)

    def test_load_rules_skips_none(self):
        rule1 = self.make_rule_file(".cursor/rules/rule1.mdc")
        with patch("rules.MdcParser.parse", return_value=None) as mock_parse:
            mdc_parser = MdcParser()
            manager = RuleManager(self.project_root, mdc_parser)
            manager.load_rules()
            self.assertEqual(manager.rules, [])

    def test_load_rules_no_rules_dirs(self):
        # No .cursor/rules directories at all
        with patch("rules.MdcParser.parse") as mock_parse:
            mdc_parser = MdcParser()
            manager = RuleManager(self.project_root, mdc_parser)
            manager.load_rules()
            self.assertEqual(manager.rules, [])
            mock_parse.assert_not_called()

    def test_load_rules_no_mdc_files(self):
        os.makedirs(os.path.join(self.project_root, ".cursor/rules"), exist_ok=True)
        # No .mdc files in the directory
        with patch("rules.MdcParser.parse") as mock_parse:
            mdc_parser = MdcParser()
            manager = RuleManager(self.project_root, mdc_parser)
            manager.load_rules()
            self.assertEqual(manager.rules, [])
            mock_parse.assert_not_called()
            def test_resolve_rule_content_no_references(self):
                mdc_parser = MdcParser()
                manager = RuleManager(self.project_root, mdc_parser)
                rule = ProjectRule(
                    name="norefs",
                    path=os.path.join(self.project_root, "dummy.mdc"),
                    rule_type=RuleType.MANUAL,
                    raw_content="No references here.",
                    referenced_files=[]
                )
                resolved = manager.resolve_rule_content(rule)
                self.assertEqual(resolved, "No references here.")

    def test_resolve_rule_content_single_reference(self):
        # Create referenced file
        ref_content = "This is file.txt content."
        rule_dir = os.path.join(self.project_root, "rulesdir")
        os.makedirs(rule_dir, exist_ok=True)
        ref_path = os.path.join(rule_dir, "file.txt")
        with open(ref_path, "w", encoding="utf-8") as f:
            f.write(ref_content)
        rule = ProjectRule(
            name="single",
            path=os.path.join(rule_dir, "rule.mdc"),
            rule_type=RuleType.MANUAL,
            raw_content="Here is @file.txt.",
            referenced_files=["file.txt"]
        )
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        resolved = manager.resolve_rule_content(rule)
        self.assertIn(ref_content, resolved)
        self.assertNotIn("@file.txt", resolved)

    def test_resolve_rule_content_multiple_references(self):
        # Create referenced files
        rule_dir = os.path.join(self.project_root, "rulesdir2")
        os.makedirs(rule_dir, exist_ok=True)
        ref1 = os.path.join(rule_dir, "file1.txt")
        ref2 = os.path.join(rule_dir, "file2.json")
        with open(ref1, "w", encoding="utf-8") as f:
            f.write("Content1")
        with open(ref2, "w", encoding="utf-8") as f:
            f.write("Content2")
        rule = ProjectRule(
            name="multi",
            path=os.path.join(rule_dir, "rule.mdc"),
            rule_type=RuleType.MANUAL,
            raw_content="A: @file1.txt B: @file2.json",
            referenced_files=["file1.txt", "file2.json"]
        )
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        resolved = manager.resolve_rule_content(rule)
        self.assertIn("Content1", resolved)
        self.assertIn("Content2", resolved)
        self.assertNotIn("@file1.txt", resolved)
        self.assertNotIn("@file2.json", resolved)

    def test_resolve_rule_content_missing_reference(self):
        rule_dir = os.path.join(self.project_root, "rulesdir3")
        os.makedirs(rule_dir, exist_ok=True)
        rule = ProjectRule(
            name="missing",
            path=os.path.join(rule_dir, "rule.mdc"),
            rule_type=RuleType.MANUAL,
            raw_content="Missing: @nofile.txt",
            referenced_files=["nofile.txt"]
        )
        mdc_parser = MdcParser()
        with patch("rules.output") as mock_output:
            manager = RuleManager(self.project_root, mdc_parser)
            resolved = manager.resolve_rule_content(rule)
            self.assertIn("[Content of 'nofile.txt' not found]", resolved)
            self.assertNotIn("@nofile.txt", resolved)
            self.assertTrue(mock_output.called)
            args, kwargs = mock_output.call_args
            self.assertEqual(args[0], "warning")
            self.assertIn("not found", args[1])

    def test_resolve_rule_content_no_recursive_resolution(self):
        # file.txt contains @another.md, but we do not resolve recursively
        rule_dir = os.path.join(self.project_root, "rulesdir4")
        os.makedirs(rule_dir, exist_ok=True)
        file_txt_path = os.path.join(rule_dir, "file.txt")
        with open(file_txt_path, "w", encoding="utf-8") as f:
            f.write("See @another.md inside file.txt")
        rule = ProjectRule(
            name="norecurse",
            path=os.path.join(rule_dir, "rule.mdc"),
            rule_type=RuleType.MANUAL,
            raw_content="Outer: @file.txt",
            referenced_files=["file.txt"]
        )
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        resolved = manager.resolve_rule_content(rule)
        self.assertIn("See @another.md inside file.txt", resolved)
        self.assertNotIn("@file.txt", resolved)

    def test_resolve_rule_content_relative_path(self):
        # Ensure referenced file is found relative to rule file
        rule_dir = os.path.join(self.project_root, "rulesdir5")
        os.makedirs(rule_dir, exist_ok=True)
        with open(os.path.join(rule_dir, "file.txt"), "w", encoding="utf-8") as f:
            f.write("RelContent")
        rule = ProjectRule(
            name="relpath",
            path=os.path.join(rule_dir, "rule.mdc"),
            rule_type=RuleType.MANUAL,
            raw_content="Rel: @file.txt",
            referenced_files=["file.txt"]
        )
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        resolved = manager.resolve_rule_content(rule)
        self.assertIn("RelContent", resolved)

    def test_get_agent_rules_info_mixed(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manager.rules = [
            ProjectRule(name="arule", path="p", rule_type=RuleType.AGENT_REQUESTED, raw_content="", description="desc1"),
            ProjectRule(name="mrule", path="p", rule_type=RuleType.MANUAL, raw_content="", description="desc2"),
            ProjectRule(name="arule2", path="p", rule_type=RuleType.ALWAYS, raw_content="", description="desc3"),
            ProjectRule(name="mrule2", path="p", rule_type=RuleType.MANUAL, raw_content="", description=None),
        ]
        info = manager.get_agent_rules_info()
        self.assertIn(("arule", "desc1"), info)
        self.assertIn(("mrule", "desc2"), info)
        self.assertNotIn(("arule2", "desc3"), info)
        self.assertNotIn(("mrule2", None), info)
        self.assertEqual(len(info), 2)

    def test_get_agent_rules_info_empty(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manager.rules = []
        info = manager.get_agent_rules_info()
        self.assertEqual(info, [])

    def test_get_manual_rule_found(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        rule = ProjectRule(name="manual1", path="p", rule_type=RuleType.MANUAL, raw_content="")
        manager.rules = [rule]
        found = manager.get_manual_rule("manual1")
        self.assertIs(found, rule)

    def test_get_manual_rule_not_found(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manager.rules = []
        found = manager.get_manual_rule("notfound")
        self.assertIsNone(found)

    def test_get_manual_rule_wrong_type(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        rule = ProjectRule(name="manual1", path="p", rule_type=RuleType.ALWAYS, raw_content="")
        manager.rules = [rule]
        found = manager.get_manual_rule("manual1")
        self.assertIsNone(found)

    def test_get_manual_rule_empty_rules(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manager.rules = []
        found = manager.get_manual_rule("anything")
        self.assertIsNone(found)

    def test_get_applicable_rules_always_only(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        always_rule = ProjectRule(name="always", path="p", rule_type=RuleType.ALWAYS, raw_content="")
        manual_rule = ProjectRule(name="manual", path="p", rule_type=RuleType.MANUAL, raw_content="")
        auto_rule = ProjectRule(name="auto", path="p", rule_type=RuleType.AUTO_ATTACHED, raw_content="")
        manager.rules = [always_rule, manual_rule, auto_rule]
        applicable = manager.get_applicable_rules([])
        self.assertEqual(applicable, [always_rule])

    def test_get_applicable_rules_only_always(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        always_rule = ProjectRule(name="always", path="p", rule_type=RuleType.ALWAYS, raw_content="")
        manager.rules = [always_rule]
        applicable = manager.get_applicable_rules([])
        self.assertEqual(applicable, [always_rule])

    def test_get_applicable_rules_no_always(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manual_rule = ProjectRule(name="manual", path="p", rule_type=RuleType.MANUAL, raw_content="")
        manager.rules = [manual_rule]
        applicable = manager.get_applicable_rules([])
        self.assertEqual(applicable, [])

    def test_get_applicable_rules_empty(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manager.rules = []
        applicable = manager.get_applicable_rules([])
        self.assertEqual(applicable, [])

    def test_get_agent_rules_info_no_matching(self):
        mdc_parser = MdcParser()
        manager = RuleManager(self.project_root, mdc_parser)
        manager.rules = [
            ProjectRule(name="arule2", path="p", rule_type=RuleType.ALWAYS, raw_content="", description="desc3"),
            ProjectRule(name="mrule2", path="p", rule_type=RuleType.MANUAL, raw_content="", description=None),
        ]
        info = manager.get_agent_rules_info()
        self.assertEqual(info, [])

if __name__ == "__main__":
    unittest.main()
