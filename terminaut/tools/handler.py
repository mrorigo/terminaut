from ..output import output
from .bash import execute_bash
from .apply_patch import execute_apply_patch

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

    tool_name = tool_call["name"]
    tool_id = tool_call.get("id", "unknown")

    if tool_name == "bash":
        if "input" not in tool_call or not isinstance(tool_call["input"], dict) or "command" not in tool_call["input"]:
            output("error", f"Invalid tool input for bash: {tool_call}")
            return {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": "Error: Missing or invalid command input"
            }

        command = tool_call["input"]["command"]

        # Prompt user for approval
        while True:
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

        return {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": output_text
        }

    elif tool_name == "apply_patch":
        if "input" not in tool_call or not isinstance(tool_call["input"], dict) or "patch_content" not in tool_call["input"]:
            output("error", f"Invalid tool input for apply_patch: {tool_call}")
            return {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": "Error: Missing or invalid patch_content input"
            }

        patch_content = tool_call["input"]["patch_content"]

        # Show patch preview
        output("tool_call", f"Apply patch with content:\n{patch_content}")

        # Prompt user for approval
        while True:
            user_resp = input("[approval] Approve applying this patch? [y/N]: ").strip().lower()
            output("approval_response", user_resp)
            if user_resp in ("y", "yes"):
                output("tool_call", "User approved patch application")
                output_text = execute_apply_patch(patch_content)
                output("summary", output_text)
                break
            elif user_resp in ("n", "no", ""):
                output("tool_call", "User denied patch application")
                output_text = "Patch application skipped by user."
                output("summary", output_text)
                break
            else:
                output("approval_prompt", "Please answer 'y' or 'n'.")

        return {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": output_text
        }

    else:
        output("error", f"Unsupported tool: {tool_name}")
        return {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": f"Error: Unsupported tool: {tool_name}"
        }
