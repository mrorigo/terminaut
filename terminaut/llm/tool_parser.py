from typing import List, Dict, Any
import re
import json

class ToolCallParser:
    """Parses tool calls from text content (custom formats and JSON)."""

    def _extract_json_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Helper: parse JSON tool calls from text/code block and XML tool_call tags"""
        tool_calls = []

        # First, extract XML-style <tool_call> blocks
        xml_tool_call_pattern = re.compile(
            r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", re.IGNORECASE
        )
        xml_matches = xml_tool_call_pattern.findall(text)

        # Remove XML tool_call blocks from text to avoid double-processing
        text_without_xml = xml_tool_call_pattern.sub("", text)

        # Process XML tool calls
        for xml_content in xml_matches:
            xml_content = xml_content.strip()
            if xml_content:
                tool_calls.extend(self._parse_json_content(xml_content))

        # Then process remaining text for code blocks and inline JSON
        # Match any code block guard (json, python, tool_call, etc.) or plain ```
        code_block_pattern = re.compile(
            r"```(?:[a-zA-Z0-9_]+)?\s*([\s\S]+?)\s*```", re.IGNORECASE
        )
        code_block_matches = code_block_pattern.findall(text_without_xml)

        # If no code blocks, consider the whole remaining text a candidate for direct JSON parsing
        candidates = code_block_matches if code_block_matches else (
            [text_without_xml] if text_without_xml.strip().startswith(("{", "[")) else []
        )

        for candidate_text in candidates:
            tool_calls.extend(self._parse_json_content(candidate_text))

        return tool_calls

    def _parse_json_content(self, content: str) -> List[Dict[str, Any]]:
        """Helper: parse JSON content and extract tool calls"""
        tool_calls = []
        content = content.strip()

        # Remove leading/trailing markdown comments or lines
        content = re.sub(r"^<!--.*?-->\s*", "", content, flags=re.DOTALL)
        content = re.sub(r"\s*<!--.*?-->$", "", content, flags=re.DOTALL)

        try:
            obj = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract the first JSON object in the content if direct parse fails
            # Use a more robust pattern to find potential JSON objects/arrays
            json_obj_pattern = re.compile(r'(\{.*?\}|\[.*?\])', re.DOTALL)
            json_match = json_obj_pattern.search(content)
            if json_match:
                try:
                    obj = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    return tool_calls  # Return empty list if parsing fails
            else:
                return tool_calls  # No JSON object found

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
                        # If string arguments fail to parse as JSON, pass as raw string
                        pass

                # Ensure arguments is a dict for consistent tool handling
                if not isinstance(args, dict):
                    from terminaut.output import output
                    output("warning", f"Tool call arguments for {item['function']['name']} not dict, was {type(args)}. Wrapping.")
                    args = {"raw_value": args}

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
                    from terminaut.output import output
                    output("warning", f"Tool call arguments for {item['name']} not dict, was {type(args)}. Wrapping.")
                    args = {"raw_value": args}

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
