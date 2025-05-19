import os
import subprocess
import re

from .output import output

def find_apply_patch_path():
    # Try to find apply_patch in the same directory as this script
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apply_patch")
    local_path = os.path.abspath(local_path)
    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path
    # Try to find apply_patch in PATH
    for dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(dir, "apply_patch")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.abspath(candidate)
    return None

APPLY_PATCH_PATH = find_apply_patch_path()
if not APPLY_PATCH_PATH:
    print("[error] Could not find apply_patch script. Please ensure it is present and executable.")

def execute_bash(command):
    """Execute a bash command and return a formatted string with the results."""
    # Rewrite apply_patch calls to use absolute path
    if APPLY_PATCH_PATH:
        # Replace 'apply_patch' at the start or after a pipe/semicolon/&&/||/newline with the absolute path
        # Only replace if it's a standalone word (not e.g. my_apply_patch)
        def patch_replacer(match):
            return match.group(1) + APPLY_PATCH_PATH
        command = re.sub(r'(^|[\s;|&])apply_patch(\s|$)', patch_replacer, command)
    else:
        if "apply_patch" in command:
            return "[error] apply_patch script not found or not executable."
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=10
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nEXIT CODE: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def handle_tool_call(tool_call):
    if tool_call is None:
        output("error", "Tool call is None, cannot process")
        return {
            "role": "tool",
            "tool_call_id": "unknown",
            "content": "Error: Tool call was None"
        }

    if "name" not in tool_call:
        output("error", f"Missing 'name' in tool_call: {tool_call}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", "unknown"),
            "content": "Error: Missing tool name"
        }

    if tool_call["name"] != "bash":
        output("error", f"Unsupported tool: {tool_call['name']}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", "unknown"),
            "content": f"Error: Unsupported tool: {tool_call['name']}"
        }

    if "input" not in tool_call or not isinstance(tool_call["input"], dict) or "command" not in tool_call["input"]:
        output("error", f"Invalid tool input: {tool_call}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", "unknown"),
            "content": "Error: Missing or invalid command input"
        }

    command = tool_call["input"]["command"]
    # output("bash_command", f"Approval required for bash command: {command}")
    output_text = ""
    # Prompt user for approval
    while True:
        # output("approval_prompt", f"Approve execution of: {command}? [y/N]: ")
        user_resp = input(f"[approval] Approve execution of {command}? [y/N]: ").strip().lower()
        output("approval_response", user_resp)
        if user_resp in ("y", "yes"):
            output("bash_command", f"User approved execution of: {command}")
            output_text = execute_bash(command)
            output("bash_output", output_text)
            break
        elif user_resp in ("n", "no", ""):
            output("bash_command", f"User denied execution of: {command}")
            output_text = "Command execution skipped by user."
            output("bash_output", output_text)
            break
        else:
            output("approval_prompt", "Please answer 'y' or 'n'.")

    # OpenAI expects tool result as a message from 'tool' role
    # For tool calls parsed from text, tool_call["id"] is generated and must be matched
    # OpenAI expects: role=tool, tool_call_id, content
    tool_response = {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "content": output_text
    }
    return tool_response

# OpenAI function definition for bash tool
bash_function = {
    "name": "bash",
    "description": "Execute bash commands and return the output",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute"
            }
        },
        "required": ["command"]
    }
}
