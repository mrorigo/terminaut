import os
import subprocess
import re

# Constants for better maintainability
APPLY_PATCH_SCRIPT_NAME = "apply_patch"
DEFAULT_TIMEOUT = 10

def find_apply_patch_path():
    """Find the apply_patch script in local directory or PATH."""
    # Check local path first
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.abspath(os.path.join(script_dir, "..", "..", APPLY_PATCH_SCRIPT_NAME))

    if _is_executable_file(local_path):
        return local_path

    # Check PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    for directory in path_dirs:
        if not directory:  # Skip empty entries
            continue
        candidate = os.path.join(directory, APPLY_PATCH_SCRIPT_NAME)
        if _is_executable_file(candidate):
            return os.path.abspath(candidate)

    return None

def _is_executable_file(path):
    """Check if path is an executable file."""
    return os.path.isfile(path) and os.access(path, os.X_OK)

def _replace_apply_patch_command(command, script_path):
    """Replace apply_patch commands with absolute path."""
    # Use word boundaries to match standalone 'apply_patch' commands
    pattern = r'\bapply_patch\b'
    return re.sub(pattern, script_path, command)

# Initialize at module level
APPLY_PATCH_PATH = find_apply_patch_path()

if not APPLY_PATCH_PATH:
    print("[error] Could not find apply_patch script. Please ensure it is present and executable.")

def execute_bash(command):
    """Execute a bash command and return a formatted string with the results."""

    # Handle apply_patch replacement
    if "apply_patch" in command:
        if not APPLY_PATCH_PATH:
            return "[error] apply_patch script not found or not executable."
        command = _replace_apply_patch_command(command, APPLY_PATCH_PATH)

    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nEXIT CODE: {result.returncode}"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {DEFAULT_TIMEOUT} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

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
