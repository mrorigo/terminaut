import os
import re
import shutil
from datetime import datetime
from typing import Dict, Any, Tuple
from ..output import output

def backup_file(filepath: str) -> bool:
    """Create a backup of the file before modifying it"""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = f"{filepath}.{timestamp}.bak"
        try:
            shutil.copy2(filepath, backup_path)
            output("info", f"Created backup: {backup_path}")
            return True
        except Exception as e:
            output("error", f"Failed to create backup for {filepath}: {e}")
            return False
    return True

def create_file(filepath: str, content: str) -> Tuple[bool, str]:
    """Create a new file with the specified content"""
    if os.path.exists(filepath):
        return False, f"File already exists: {filepath}"

    try:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)

        # Write content to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True, f"Created file: {filepath}"
    except Exception as e:
        return False, f"Failed to create {filepath}: {e}"

def update_file(filepath: str, old_text: str, new_text: str) -> Tuple[bool, str]:
    """Replace specified text in a file"""
    if not os.path.exists(filepath):
        return False, f"File does not exist: {filepath}"

    try:
        # Create backup
        if not backup_file(filepath):
            return False, f"Failed to backup {filepath}"

        # Read current content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if old_text exists
        if old_text not in content:
            return False, f"Could not find text to update in {filepath}:\n---\n{old_text}\n---"

        # Replace text
        content = content.replace(old_text, new_text)

        # Write updated content
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True, f"Updated text in: {filepath}"
    except Exception as e:
        return False, f"Failed to update {filepath}: {e}"

def insert_before(filepath: str, marker_text: str, insert_text: str) -> Tuple[bool, str]:
    """Insert text before specified marker text"""
    if not os.path.exists(filepath):
        return False, f"File does not exist: {filepath}"

    try:
        # Create backup
        if not backup_file(filepath):
            return False, f"Failed to backup {filepath}"

        # Read current content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if marker_text exists
        if marker_text not in content:
            return False, f"Could not find marker text for insert_before in {filepath}:\n---\n{marker_text}\n---"

        # Insert text
        content = content.replace(marker_text, insert_text + marker_text)

        # Write updated content
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True, f"Inserted text before marker in: {filepath}"
    except Exception as e:
        return False, f"Failed to insert before marker in {filepath}: {e}"

def insert_after(filepath: str, marker_text: str, insert_text: str) -> Tuple[bool, str]:
    """Insert text after specified marker text"""
    if not os.path.exists(filepath):
        return False, f"File does not exist: {filepath}"

    try:
        # Create backup
        if not backup_file(filepath):
            return False, f"Failed to backup {filepath}"

        # Read current content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if marker_text exists
        if marker_text not in content:
            return False, f"Could not find marker text for insert_after in {filepath}:\n---\n{marker_text}\n---"

        # Insert text
        content = content.replace(marker_text, marker_text + insert_text)

        # Write updated content
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True, f"Inserted text after marker in: {filepath}"
    except Exception as e:
        return False, f"Failed to insert after marker in {filepath}: {e}"

def delete_text(filepath: str, text_to_delete: str) -> Tuple[bool, str]:
    """Delete specified text from file"""
    if not os.path.exists(filepath):
        return False, f"File does not exist: {filepath}"

    try:
        # Create backup
        if not backup_file(filepath):
            return False, f"Failed to backup {filepath}"

        # Read current content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if text_to_delete exists
        if text_to_delete not in content:
            return False, f"Could not find text to delete in {filepath}:\n---\n{text_to_delete}\n---"

        # Delete text
        content = content.replace(text_to_delete, "")

        # Write updated content
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True, f"Deleted text from: {filepath}"
    except Exception as e:
        return False, f"Failed to delete text from {filepath}: {e}"

def parse_patch_blocks(patch_text: str) -> list[str]:
    """
    Parse the patch text into individual patch blocks.
    Each patch block is contained between "*** Begin Patch" and "*** End Patch".
    """
    pattern = re.compile(
        r"\*\*\* Begin Patch\r?\n([\s\S]*?)\r?\n\*\*\* End Patch",
        re.MULTILINE
    )
    return pattern.findall(patch_text)

def process_patch_block(block_text: str) -> Tuple[bool, str]:
    """Process a single patch block"""
    lines = block_text.splitlines()
    i = 0
    results = []
    success = True

    while i < len(lines):
        line = lines[i]

        # Operation markers
        if line.startswith("*** ") and ":" in line:
            operation, rest = line[4:].split(":", 1)
            operation = operation.strip().lower()
            filepath = rest.strip()

            # Move to the next line
            i += 1

            # Extract content based on the operation
            if operation == "create":
                # Collect all content until the next operation or end
                content_lines = []
                while i < len(lines) and not lines[i].startswith("*** "):
                    content_lines.append(lines[i])
                    i += 1
                content = "\n".join(content_lines)
                op_success, message = create_file(filepath, content)
                success &= op_success
                results.append(message)

            elif operation in ["update", "insert_before", "insert_after", "delete"]:
                # For these operations, we need to find delimiter lines
                old_text_lines = []
                new_text_lines = []

                # Find the "old_text:" marker
                while i < len(lines) and not lines[i].strip() == "old_text:":
                    i += 1

                # If we found it, collect old text lines
                if i < len(lines):
                    i += 1  # Move past the marker
                    while i < len(lines) and not (lines[i].startswith("*** ") or lines[i].strip() == "new_text:"):
                        old_text_lines.append(lines[i])
                        i += 1

                # If this is not a delete operation, look for "new_text:" marker
                if operation != "delete":
                    while i < len(lines) and not lines[i].strip() == "new_text:":
                        i += 1

                    # If we found it, collect new text lines
                    if i < len(lines):
                        i += 1  # Move past the marker
                        while i < len(lines) and not lines[i].startswith("*** "):
                            new_text_lines.append(lines[i])
                            i += 1

                # Combine the lines into text blocks
                old_text = "\n".join(old_text_lines)
                new_text = "\n".join(new_text_lines)

                # Apply the appropriate operation
                if operation == "update":
                    op_success, message = update_file(filepath, old_text, new_text)
                elif operation == "insert_before":
                    op_success, message = insert_before(filepath, old_text, new_text)
                elif operation == "insert_after":
                    op_success, message = insert_after(filepath, old_text, new_text)
                elif operation == "delete":
                    op_success, message = delete_text(filepath, old_text)

                success &= op_success
                results.append(message)
            else:
                message = f"Unknown operation: {operation}"
                results.append(message)
                i += 1
                success = False
        else:
            i += 1

    return success, "\n".join(results)

def execute_apply_patch(patch_content: str) -> str:
    """Execute apply_patch with the given patch content"""
    try:
        blocks = parse_patch_blocks(patch_content)

        if not blocks:
            return "Error: No patch blocks found in input"

        all_results = []
        all_success = True

        for block in blocks:
            success, result = process_patch_block(block)
            all_success &= success
            all_results.append(result)

        final_result = "\n".join(all_results)

        if all_success:
            final_result = "Patch applied successfully.\n" + final_result
        else:
            final_result = "Some patch operations failed.\n" + final_result

        return final_result

    except Exception as e:
        return f"Error processing patch: {str(e)}"

# OpenAI function definition for apply_patch tool
apply_patch_function = {
    "name": "apply_patch",
    "description": "Apply file modifications using patch format with operations like create, update, insert_before, insert_after, and delete",
    "parameters": {
        "type": "object",
        "properties": {
            "patch_content": {
                "type": "string",
                "description": "The patch content in the format expected by apply_patch, including *** Begin Patch and *** End Patch markers"
            }
        },
        "required": ["patch_content"]
    }
}
