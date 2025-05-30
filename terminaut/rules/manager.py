from typing import Optional
from .types import ProjectRule, RuleType
from .parser import MdcParser
from terminaut.output import output
import os
import fnmatch


class RuleManager:
    def __init__(self, project_root: str, mdc_parser: MdcParser):
        self.project_root = project_root
        self.mdc_parser = mdc_parser
        self.rules: list[ProjectRule] = []

    def load_rules(self):
        found_rule_files = []
        # Walk the project root to find all .cursor/rules/ directories
        for dirpath, dirnames, filenames in os.walk(self.project_root):
            # Check if this directory is a .cursor/rules directory
            if os.path.basename(dirpath) == "rules" and os.path.basename(os.path.dirname(dirpath)) == ".cursor":
                # Find all .mdc files in this directory (non-recursive)
                for fname in os.listdir(dirpath):
                    if fname.endswith(".mdc"):
                        abs_path = os.path.join(dirpath, fname)
                        rule_name = os.path.splitext(fname)[0]
                        found_rule_files.append((abs_path, rule_name))
        loaded_count = 0
        for abs_path, rule_name in found_rule_files:
            rule = self.mdc_parser.parse(abs_path, rule_name)
            if rule is not None:
                self.rules.append(rule)
                loaded_count += 1
        if loaded_count > 0:
            output("info", f"Loaded {loaded_count} project rule(s) from .cursor/rules directories:")
            for rule in self.rules:
                output("info_detail", f"- {rule.description or rule.name} ({rule.rule_type})")
        else:
            output("info", "No rules loaded from .cursor/rules directory")

    def resolve_rule_content(self, rule: ProjectRule) -> str:
        resolved_content = rule.raw_content
        for ref_file_name in rule.referenced_files:
            ref_path = os.path.join(os.path.dirname(rule.path), ref_file_name)
            try:
                with open(ref_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                # Replace all occurrences of @ref_file_name with file_content
                # Use regex to ensure only @ref_file_name is replaced (not e.g. part of a larger word)
                import re
                resolved_content = re.sub(
                    rf"(?<!\w)@{re.escape(ref_file_name)}\b",
                    file_content,
                    resolved_content
                )
            except FileNotFoundError:
                output("warning", f"Referenced file {ref_file_name} not found for rule {rule.name}")
                placeholder = f"[Content of '{ref_file_name}' not found]"
                import re
                resolved_content = re.sub(
                    rf"(?<!\w)@{re.escape(ref_file_name)}\b",
                    placeholder,
                    resolved_content
                )
            except IOError:
                output("warning", f"Could not read referenced file {ref_file_name} for rule {rule.name}")
                placeholder = f"[Content of '{ref_file_name}' not found]"
                import re
                resolved_content = re.sub(
                    rf"(?<!\w)@{re.escape(ref_file_name)}\b",
                    placeholder,
                    resolved_content
                )
        return resolved_content

    def get_agent_rules_info(self) -> list[tuple[str, str]]:
        info = []
        for rule in self.rules:
            if rule.rule_type in (RuleType.AGENT_REQUESTED, RuleType.MANUAL) and rule.description:
                info.append((rule.name, rule.description))
        return info

    def get_manual_rule(self, name: str) -> Optional[ProjectRule]:
        """
        Get a rule that can be manually invoked by name.
        Any rule that is not ALWAYS can be manually invoked.
        """
        for rule in self.rules:
            if rule.name == name and rule.rule_type != RuleType.ALWAYS:
                return rule
        return None

    def get_applicable_rules(self, active_context_files: list[str]) -> list[ProjectRule]:
        applicable = []
        seen = set()
        # ALWAYS rules
        for rule in self.rules:
            rule_id = (rule.name, rule.path)
            if rule.rule_type == RuleType.ALWAYS and rule_id not in seen:
                applicable.append(rule)
                seen.add(rule_id)

        # AUTO_ATTACHED rules
        for rule in self.rules:
            rule_id = (rule.name, rule.path)
            if rule.rule_type == RuleType.AUTO_ATTACHED and rule_id not in seen:
                for glob_pattern in rule.globs:
                    for file_path in active_context_files:
                        # Match against full path (relative or absolute), as per spec
                        if fnmatch.fnmatch(file_path, glob_pattern):
                            applicable.append(rule)
                            seen.add(rule_id)
                            break
                    if rule_id in seen:
                        break
        return applicable
