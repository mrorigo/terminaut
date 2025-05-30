import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from terminaut.rules.manager import RuleManager

class SystemPromptConstructor:
     """Constructs the dynamic system prompt based on rules and context."""
     def __init__(self, base_system_prompt: str, rule_manager: Optional[RuleManager]):
         self._base_system_prompt = base_system_prompt
         self._rule_manager = rule_manager
         self._agent_rules_info_section = self._build_agent_rules_info()

     def _build_agent_rules_info(self) -> str:
         """Precomputes the section listing available agent/manual rules."""
         if self._rule_manager is None:
             return ""

         agent_rules = self._rule_manager.get_agent_rules_info()
         if not agent_rules:
             return ""

         rules_section = (
             "\nThe following project rules are available and can be manually invoked using @RuleName:\n"
         )
         for name, desc in agent_rules:
             rules_section += f"- {name}: {desc}\n"
         rules_section += "(Agent-requested rules will be considered by the assistant if relevant.)\n"
         return rules_section

     def _determine_active_context_files(self, messages: List[Dict[str, Any]]) -> List[str]:
         """
         Extract file paths/names from the latest user message content.
         Returns a list of strings.
         """
         user_content = None
         for msg in reversed(messages):
             if msg.get("role") == "user" and "content" in msg:
                 user_content = msg["content"]
                 break
         if not user_content:
             return []
         # Regex: match things like main.py, ./foo/bar.txt, foo-bar.js, etc.
         # Added boundary \b to prevent matching parts of words, e.g., "@user.name"
         matches = re.findall(r'\b([\.\/\w-]+\.\w+)\b', user_content)
         return matches

     def _expand_template_variables(self, text: str) -> str:
         """
         Expand template variables in the system prompt.
         Supported variables: {{date}}, {{time}}, {{weekday}}
         """
         now = datetime.now()

         # Define template variables
         template_vars = {
             'date': now.strftime('%Y-%m-%d'),
             'time': now.strftime('%H:%M:%S'),
             'weekday': now.strftime('%A')
         }

         # Replace template variables using regex
         def replace_var(match):
             var_name = match.group(1)
             return template_vars.get(var_name, match.group(0))  # Return original if not found

         # Pattern matches {{variable_name}}
         expanded_text = re.sub(r'\{\{(\w+)\}\}', replace_var, text)
         return expanded_text

     def build_system_prompt(self, current_input_messages: List[Dict[str, Any]], manual_rule_names: List[str]) -> str:
         """
         Builds the full system prompt for the current API call.
         Includes base prompt, applicable rules, and agent rules info.
         """
         # Expand template variables in the base prompt first
         base_prompt_expanded = self._expand_template_variables(self._base_system_prompt.rstrip())
         system_prompt_parts = [base_prompt_expanded]

         if self._rule_manager:
             # Determine active context files from the *current input* messages
             active_context_files = self._determine_active_context_files(current_input_messages)
             # output("info_detail", f"Active context files: {active_context_files}") # Excessive logging

             # Get automatically applicable rules (ALWAYS and AUTO_ATTACHED)
             applicable_rules = self._rule_manager.get_applicable_rules(active_context_files)

             # Add manually invoked rules if any
             manually_invoked_rules = []
             for rule_name in manual_rule_names:
                 rule = self._rule_manager.get_manual_rule(rule_name)
                 if rule:
                     manually_invoked_rules.append(rule)
                 # Warning for not found manual rules is handled in cli.py

             # Combine auto and manually invoked rules, avoiding duplicates
             all_rules: List[ProjectRule] = list(applicable_rules)
             seen_rules = {(r.name, r.path) for r in applicable_rules} # Use name and path for uniqueness

             for rule in manually_invoked_rules:
                 if (rule.name, rule.path) not in seen_rules:
                     all_rules.append(rule)
                     seen_rules.add((rule.name, rule.path))

             # Debug log applied rules
             # output("info_detail", f"Applied Rules: {[rule.name for rule in all_rules]}") # Excessive logging

             # Append applied rules content
             if all_rules:
                 for rule in all_rules:
                     resolved_content = self._rule_manager.resolve_rule_content(rule)
                     # Also expand template variables in rule content
                     resolved_content = self._expand_template_variables(resolved_content)
                     system_prompt_parts.append(
                         f"\n\nApplied Project Rule: {rule.name}\n---\n{resolved_content}\n---"
                     )

             # Append agent/manual rules info section (if any)
             if self._agent_rules_info_section:
                  system_prompt_parts.append("\n" + self._agent_rules_info_section)

         return "\n".join(system_prompt_parts)
