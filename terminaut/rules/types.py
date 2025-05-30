
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

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
