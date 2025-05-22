from dataclasses import dataclass, field

import os
import fnmatch
import re
from typing import List, Optional
from enum import Enum
from terminaut.output import output
import yaml

class RuleType(Enum):
    ALWAYS = "ALWAYS"
    AUTO_ATTACHED = "AUTO_ATTACHED"
    AGENT_REQUESTED = "AGENT_REQUESTED"
    MANUAL = "MANUAL"

@dataclass
class ProjectRule:
    name: str  # filename without .mdc extension
    path: str  # absolute path to the .mdc file
    rule_type: 'RuleType'
    raw_content: str  # content part of the .mdc, after frontmatter
    description: Optional[str] = None
    globs: List[str] = field(default_factory=list)
    always_apply: bool = False
    referenced_files: List[str] = field(default_factory=list)  # paths relative to the rule filefrom dataclasses import dataclass, field


class MdcParser:
    def parse(self, file_path: str, rule_name: str) -> Optional[ProjectRule]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            output("error", f"Rule file not found: {file_path}")
            return None

        # Split frontmatter and main content
        lines = content.splitlines(keepends=True)
        frontmatter = ""
        main_content = content

        # Find all lines with only '---'
        dash_indices = [i for i, line in enumerate(lines) if line.strip() == "---"]
        if len(dash_indices) >= 2:
            # Frontmatter is between first and second ---
            frontmatter = "".join(lines[dash_indices[0]+1:dash_indices[1]])
            main_content = "".join(lines[dash_indices[1]+1:])
        else:
            # No or less than 2 ---: all is main content
            frontmatter = ""
            main_content = content

        # Default metadata
        description = None
        globs = []
        always_apply = False

        # Parse YAML frontmatter if present
        if frontmatter.strip():
            try:
                meta = yaml.safe_load(frontmatter)
                if isinstance(meta, dict):
                    description = meta.get("description")
                    globs = meta.get("globs", [])
                    if globs and not isinstance(globs, list):
                        globs = [globs]
                    always_apply = bool(meta.get("alwaysApply", False))
                else:
                    # If YAML is not a dict, treat as no metadata
                    output("error", f"Frontmatter YAML is not a dict in {file_path}")
            except yaml.YAMLError as e:
                output("error", f"YAML parsing error in {file_path}: {e}")
                # Proceed with defaults
        else:
            output("warning", f"Frontmatter header not found in {file_path}")


        # Infer rule_type
        if always_apply:
            rule_type = RuleType.ALWAYS
        elif globs:
            rule_type = RuleType.AUTO_ATTACHED
        elif description:
            rule_type = RuleType.AGENT_REQUESTED
        else:
            rule_type = RuleType.MANUAL

        # Extract @file references from main_content (not part of emails etc.)
        referenced_files = re.findall(r"(?<!\w)@([\w\.-]+\.\w+)", main_content)

        rule = ProjectRule(
            name=rule_name,
            path=file_path,
            rule_type=rule_type,
            raw_content=main_content,
            description=description,
            globs=globs,
            always_apply=always_apply,
            referenced_files=referenced_files
        )
        return rule


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
