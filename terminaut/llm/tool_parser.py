from typing import List, Dict, Any
import re

class ToolCallParser:
    """Parses tool calls from text content (custom formats and JSON)."""

    def _extract_json_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Helper: parse JSON tool calls from text/code block"""
        tool_calls = []
        # Match any code block guard (json, python, tool_call, etc.) or plain ```
        # Also handle inline JSON that might not be in a code block
        code_block_pattern = re.compile(
            r"```(?:[a-zA-Z0-9_]+)?\s*([\s\S]+?)\s*```", re.IGNORECASE
        )
        matches = code_block_pattern.findall(text)
        # If no code blocks, consider the whole text a candidate for direct JSON parsing
        candidates = matches if matches else ([text] if text.strip().startswith(("{", "[")) else [])

        for candidate_text in candidates:
            candidate_text = candidate_text.strip()
            # Sometimes the code block may contain extra markdown or comments, try to extract JSON object
            # Remove leading/trailing markdown comments or lines
            candidate_text = re.sub(r"^<!--.*?-->\s*", "", candidate_text, flags=re.DOTALL)
            candidate_text = re.sub(r"\s*<!--.*?-->$", "", candidate_text, flags=re.DOTALL)
            try:
                obj = json.loads(candidate_text)
            except json.JSONDecodeError:
                # Try to extract the first JSON object in the candidate if direct parse fails
                # Use a more robust pattern to find potential JSON objects/arrays
                json_obj_pattern = re.compile(r'(\{.*?\}|\[.*?\])', re.DOTALL)
                json_match = json_obj_pattern.search(candidate_text)
                if json_match:
                    try:
                        obj = json.loads(json_match.group(1)) # Use group(1) for the captured content
                    except json.JSONDecodeError:
                        continue # Not a valid JSON object
                else:
                    continue # No JSON object found

            objs_to_process = obj if isinstance(obj, list) else [obj]
            for item in objs_to_process:
                # Accept OpenAI tool_call format within text
                if (isinstance(item, dict) and "function" in item and
                    isinstance(item["function"], dict) and "name" in item["function"] and
                    "arguments" in item["function"]):
                    args = item["function"]["arguments"]
                    # Arguments can be a string (needs parsing) or already a dict/list
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            # If string arguments fail to parse as JSON, pass as raw string under a specific key
                            # For bash, command is string, but the tool expects {"command": "..."}.
                            # If the model puts the command string directly in 'arguments', this will wrap it.
                            # If the tool expects a string, it should be handled in handle_tool_call.
                            pass # Keep as string if JSON decode fails here

                    # Ensure arguments is a dict for consistent tool handling
                    if not isinstance(args, dict):
                         output("warning", f"Tool call arguments for {item['function']['name']} not dict, was {type(args)}. Wrapping.")
                         args = {"raw_value": args} # Wrap non-dict args

                    tool_calls.append({"name": item["function"]["name"], "arguments": args})
                # Accept simple {"name": ..., "arguments": ...} format within text
                elif isinstance(item, dict) and "name" in item and "arguments" in item:
                    args = item["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            pass

                    if not isinstance(args, dict):
                         output("warning", f"Tool call arguments for {item['name']} not dict, was {type(args)}. Wrapping.")
                         args = {"raw_value": args} # Wrap non-dict args

                    tool_calls.append({"name": item["name"], "arguments": args})

        return tool_calls

    def extract_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts tool calls from text, supporting custom apply_patch format and JSON formats.
        Returns a list of tool call dictionaries in a standardized format:
        {"name": "tool_name", "arguments": {"arg1": "value1", ...}}
        """
        all_tool_calls: List[Dict[str, Any]] = []
        remaining_text_segments: List[str] = []
        current_pos = 0

        # Regex for the custom apply_patch format (custom patch block)
        # This regex looks for "apply_patch" on a line, followed by
        # a block starting with "*** Begin Patch" and ending with "*** End Patch".
        # It captures the block from "*** Begin Patch" to "*** End Patch" (inclusive).
        apply_patch_pattern = re.compile(
            r"^apply_patch\r?\n(\*\*\* Begin Patch\r?\n[\s\S]*?\r?\n\*\*\* End Patch)(?:\r?\n|$)",
            re.MULTILINE
        )

        for match in apply_patch_pattern.finditer(text):
            # Add text segment before this match
            if match.start() > current_pos:
                remaining_text_segments.append(text[current_pos:match.start()])

            # Process the apply_patch block
            patch_block = match.group(1)
            # No validation needed; just pass the block as-is (including markers)
            # Need to escape single quotes for the bash command echo ''
            escaped_patch_content = patch_block.replace("'", "'\\''")
            command_str = f"echo '{escaped_patch_content}' | apply_patch"

            # The arguments for the bash tool must be a dict with a "command" key
            all_tool_calls.append({
                "name": "bash",
                "arguments": {"command": command_str}
            })

            current_pos = match.end()

        # Add any remaining text after the last match
        if current_pos < len(text):
            remaining_text_segments.append(text[current_pos:])

        # Process remaining text segments for JSON tool calls
        for segment in remaining_text_segments:
            if segment.strip(): # Only process non-empty segments
                json_calls = self._extract_json_tool_calls(segment)
                all_tool_calls.extend(json_calls)

        return all_tool_calls
