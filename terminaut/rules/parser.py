import re
import yaml
from typing import Optional
from .types import ProjectRule, RuleType
from terminaut.output import output

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
