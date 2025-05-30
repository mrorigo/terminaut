from ..output import output
from .bash import execute_bash

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
