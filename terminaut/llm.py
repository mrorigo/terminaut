import os
import json
import re
import uuid
import openai

from .output import output
from .tools import bash_function

HISTORY_LIMIT = max(3, int(os.environ.get("HISTORY_LIMIT", "20")))

class LLM:
    def __init__(self, model, base_url=None, system_prompt=None):
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError("OPENAI_API_KEY environment variable not found.")
        self.model = model
        self.messages = []
        # Use provided system prompt, or load from file, or fallback to default
        if system_prompt is not None:
            self.system_prompt = system_prompt
        else:
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system-prompt.md")
            local_path = os.path.abspath(local_path)

            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    self.system_prompt = f.read()
            except Exception as e:
                output("error", f"Failed to read system prompt: {e}")
                self.system_prompt = "You are a helpful AI assistant."
        self.functions = [bash_function]
        self.client = openai.OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=base_url
        ) if base_url else openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def __call__(self, content, stream=True):
        # content is a list of messages (role/content dicts)
        self.messages.extend(content)

        # --- Normalize self.messages: Ensure the system prompt is always the first message ---
        # Remove all existing system messages
        self.messages = [msg for msg in self.messages if msg.get("role") != "system"]

        # Prepend the system prompt as the first message
        self.messages.insert(0, {"role": "system", "content": self.system_prompt})

        # Assert that the first message is the system message
        assert self.messages[0].get("role") == "system", "The first message in self.messages must always have the role 'system'."

        # --- History Truncation (if needed) ---
        # HISTORY_LIMIT is guaranteed to be >= 3 by __init__
        if len(self.messages) > HISTORY_LIMIT:
            # The system message is always the first message and is always kept
            system_msg = self.messages[0]

            # Messages to consider for truncation are all non-system messages
            messages_to_consider = self.messages[1:]

            # Number of non-system messages we can keep
            num_non_system_to_keep = HISTORY_LIMIT - 1  # At least 2

            # Find the first user message (if any)
            initial_user_idx = next(
                (i for i, msg in enumerate(messages_to_consider) if msg.get("role") == "user"),
                None
            )

            kept_non_system_messages = []
            # Prioritize initial user message
            if initial_user_idx is not None:
                kept_non_system_messages.append(messages_to_consider[initial_user_idx])

            # Collect other messages, excluding the initial user message if it was already added
            other_messages = [
                msg for i, msg in enumerate(messages_to_consider)
                if initial_user_idx is None or i != initial_user_idx
            ]

            # Fill remaining slots with the most recent other messages
            num_slots_for_others = num_non_system_to_keep - len(kept_non_system_messages)
            if num_slots_for_others > 0 and other_messages:
                # Add most recent other messages
                # If initial_user_idx was present, kept_non_system_messages already has it.
                # We need to insert these chronologically relative to the initial user message.

                # This logic is simpler: take all candidates, sort by original index, keep required number
                # Build a list of (original_index_in_messages_to_consider, message_object)
                candidates_with_indices = []
                if initial_user_idx is not None:
                    candidates_with_indices.append((initial_user_idx, messages_to_consider[initial_user_idx]))

                # Add recent N other messages
                # Number of other messages to pick:
                num_other_messages_to_pick = num_non_system_to_keep - (1 if initial_user_idx is not None else 0)

                # Get indices of messages that are not the initial_user_idx
                other_indices = [i for i, _ in enumerate(messages_to_consider) if i != initial_user_idx]

                # Pick the last num_other_messages_to_pick from these other_indices
                indices_of_others_to_keep = other_indices[-num_other_messages_to_pick:] if num_other_messages_to_pick > 0 else []

                for i in indices_of_others_to_keep:
                    candidates_with_indices.append((i, messages_to_consider[i]))

                # Sort by original index to maintain order
                candidates_with_indices.sort(key=lambda x: x[0])
                kept_non_system_messages = [msg for _, msg in candidates_with_indices]


            # Update self.messages with the system message and the kept messages
            self.messages = [system_msg] + kept_non_system_messages

        # At this point, self.messages is correctly formatted and truncated.
        # Assert that the first message is still the system message
        assert self.messages[0].get("role") == "system", "After truncation, the first message in self.messages must still have the role 'system'."

        # It starts with a system prompt and respects HISTORY_LIMIT.
        api_call_messages = self.messages

        print(f"api_call_messages: {json.dumps(api_call_messages, indent=True)}")

        tools = [{"type": "function", "function": func} for func in self.functions]

        try:
            if stream:
                return self._stream_response(api_call_messages, tools)
            else:
                return self._non_stream_response(api_call_messages, tools)
        except Exception as e:
            output("error", f"OpenAI API error: {str(e)}")
            # Print the full exception details for debugging
            import traceback
            output("error", f"Full error details: {traceback.format_exc()}")
            return f"Error calling OpenAI API: {str(e)}", []

    def _extract_json_tool_calls(self, text):
        """Helper: parse JSON tool calls from text/code block"""
        tool_calls = []
        # Match any code block guard (json, python, tool_call, etc.) or plain ```
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
                json_obj_pattern = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]") # Match first JSON object or array
                json_match = json_obj_pattern.search(candidate_text)
                if json_match:
                    try:
                        obj = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        continue # Not a valid JSON object
                else:
                    continue # No JSON object found

            objs_to_process = obj if isinstance(obj, list) else [obj]
            for item in objs_to_process:
                # Accept OpenAI tool_call format
                if (isinstance(item, dict) and "function" in item and
                    isinstance(item["function"], dict) and "name" in item["function"] and
                    "arguments" in item["function"]):
                    args = item["function"]["arguments"]
                    # Arguments can be a string (needs parsing) or already a dict/list
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            # If string arguments fail to parse as JSON, keep as string
                            # or handle as per tool's expectation. For bash, command is string.
                            # For now, let's assume if it's a string, it's meant to be.
                            # However, for structured tools, it should be valid JSON.
                            # This part might need refinement based on how tools expect string args.
                            pass
                    tool_calls.append({"name": item["function"]["name"], "arguments": args})
                # Accept simple {"name": ..., "arguments": ...}
                elif isinstance(item, dict) and "name" in item and "arguments" in item:
                    args = item["arguments"]
                    # Similar handling for arguments if they are strings
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            pass
                    tool_calls.append({"name": item["name"], "arguments": args})

        # Fallback: If no tool calls found via code blocks or direct parsing of `text` (if it was a candidate)
        # try to find any JSON object directly in the text. This is for cases where JSON is not in a code block.
        # This should only run if `candidates` was `[text]` and yielded nothing, or `candidates` was empty.
        if not tool_calls and ( (candidates == [text] and text.strip().startswith(("{", "["))) or not candidates ):
            json_obj_pattern = re.compile(r"\{[\s\S]*?\}|\[[\s\S]*?\]") # Find all JSON objects or arrays
            for match_str in json_obj_pattern.findall(text):
                try:
                    item = json.loads(match_str)
                    # Process item (can be dict or list)
                    objs_to_process = item if isinstance(item, list) else [item]
                    for o in objs_to_process:
                        if (isinstance(o, dict) and "function" in o and
                            isinstance(o["function"], dict) and "name" in o["function"] and
                            "arguments" in o["function"]):
                            args = o["function"]["arguments"]
                            if isinstance(args, str):
                                try: args = json.loads(args)
                                except json.JSONDecodeError: pass
                            tool_calls.append({"name": o["function"]["name"], "arguments": args})
                        elif isinstance(o, dict) and "name" in o and "arguments" in o:
                            args = o["arguments"]
                            if isinstance(args, str):
                                try: args = json.loads(args)
                                except json.JSONDecodeError: pass
                            tool_calls.append({"name": o["name"], "arguments": args})
                except json.JSONDecodeError:
                    continue
        return tool_calls

    def extract_tool_calls_from_text(self, text):
        """Extracts tool calls from text, supporting custom apply_patch format and JSON formats."""
        all_tool_calls = []
        remaining_text_segments = []
        current_pos = 0

        # Regex for the custom apply_patch format (custom patch block)
        # This regex looks for "apply_patch" on a line, followed by
        # a block starting with "*** Begin Patch" and ending with "*** End Patch".
        # It captures the block from "*** Begin Patch" to "*** End Patch" (inclusive).
        apply_patch_pattern = re.compile(
            r"^apply_patch\r?\n(\*\*\* Begin Patch\r?\n[\s\S]*?\r?\n\*\*\* End Patch)$",
            re.MULTILINE
        )

        for match in apply_patch_pattern.finditer(text):
            # Add text segment before this match
            if match.start() > current_pos:
                remaining_text_segments.append(text[current_pos:match.start()])

            # Process the apply_patch block
            patch_block = match.group(1)
            # No validation needed; just pass the block as-is (including markers)
            escaped_patch_content = patch_block.replace("'", "'\\''")
            command_str = f"echo '{escaped_patch_content}' | apply_patch"

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

    def _stream_response(self, messages, tools):
        """Process a streaming response from the API"""
        import time
        # from .output import output # Already imported at class level

        # State for accumulating the response
        accumulated_content = ""
        accumulated_tool_calls = []
        # tool_call_in_progress = {} # Not used with current OpenAI stream structure
        current_tool_call_chunks = {} # For structured tool calls from stream

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto", # Explicitly "auto" is fine
                max_tokens=2000, # Consider making this configurable
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices: # Handle empty choices list
                    continue

                delta = chunk.choices[0].delta

                if hasattr(delta, 'content') and delta.content is not None:
                    accumulated_content += delta.content
                    output("stream", delta.content) # Stream content out immediately

                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tool_call_chunk in delta.tool_calls:
                        index = tool_call_chunk.index
                        if index not in current_tool_call_chunks:
                            current_tool_call_chunks[index] = {
                                "id": "", "type": "function",
                                "function": {"name": "", "arguments": ""}
                            }

                        tc_data = current_tool_call_chunks[index]
                        if tool_call_chunk.id:
                            tc_data["id"] += tool_call_chunk.id
                        # type is usually 'function', can be pre-filled or updated if provided
                        # if tool_call_chunk.type:
                        #    tc_data["type"] += tool_call_chunk.type
                        if tool_call_chunk.function:
                            if tool_call_chunk.function.name:
                                tc_data["function"]["name"] += tool_call_chunk.function.name
                            if tool_call_chunk.function.arguments:
                                tc_data["function"]["arguments"] += tool_call_chunk.function.arguments

                if chunk.choices[0].finish_reason is not None:
                    # Could be "stop", "tool_calls", "length", etc.
                    break

                time.sleep(0.01) # Small delay, might not be necessary

            # Process fully assembled structured tool calls
            for _index, tc_chunk_data in current_tool_call_chunks.items():
                if tc_chunk_data["id"] and tc_chunk_data["function"]["name"]:
                    try:
                        args_str = tc_chunk_data["function"]["arguments"]
                        parsed_args = {}
                        if args_str:
                            try:
                                parsed_args = json.loads(args_str)
                            except json.JSONDecodeError:
                                # If args are not valid JSON, pass as raw string under a specific key
                                # or handle as per tool's expectation. For bash, it's fine.
                                parsed_args = {"raw_arguments": args_str}
                                output("warning", f"Tool call arguments for {tc_chunk_data['function']['name']} not valid JSON: {args_str}")

                        accumulated_tool_calls.append({
                            "id": tc_chunk_data["id"],
                            "name": tc_chunk_data["function"]["name"],
                            "input": parsed_args, # This is the dict of arguments
                            "from_text_block": False # Indicates it's a structured tool call
                        })
                    except Exception as e:
                        output("error", f"Error processing structured tool call: {e}")

            # Search for tool calls in the accumulated text content (custom apply_patch and JSON)
            # This should run IF there's content OR if finish_reason wasn't 'tool_calls'
            # (meaning LLM might have mixed text and tool calls, or just text with embedded calls)
            if accumulated_content:
                extracted_text_tool_calls = self.extract_tool_calls_from_text(accumulated_content)
                for tc in extracted_text_tool_calls:
                    tool_call_id = f"manual_{tc.get('name', 'unknown')}_{uuid.uuid4().hex[:8]}"
                    # tc["arguments"] should be a dict from extract_tool_calls_from_text
                    args = tc.get("arguments", {})
                    if not isinstance(args, dict): # Should be a dict from our extractors
                        output("warning", f"Text-extracted tool call arguments not a dict: {args}. Wrapping.")
                        args = {"value": args} # Fallback wrapping

                    accumulated_tool_calls.append({
                        "id": tool_call_id,
                        "name": tc["name"],
                        "input": args, # This is the dict of arguments
                        "from_text_block": True
                    })

            # Add the assistant's response message to history
            # This needs to be structured correctly for OpenAI's history format
            assistant_message_to_log = {"role": "assistant", "tool_calls": []}
            if accumulated_content: # Content always comes first
                assistant_message_to_log["content"] = accumulated_content

            # Include ALL tool calls in the history, both structured and extracted from text
            # This ensures that when tool responses come back, they can be matched with tool calls
            if accumulated_tool_calls:
                # Explicitly create the tool_calls list first, then assign it to the message
                tool_calls_for_log = []
                for tc in accumulated_tool_calls:
                    tool_call_entry = {
                        "id": tc["id"],
                        "type": "function",  # Assuming all are functions
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["input"])  # Arguments should be stringified JSON
                        }
                    }
                    tool_calls_for_log.append(tool_call_entry)

                # Now assign the constructed list
                assistant_message_to_log["tool_calls"] = tool_calls_for_log

            # Only add message if it has content or tool calls
            if "content" in assistant_message_to_log or "tool_calls" in assistant_message_to_log:
                 self.messages.append(assistant_message_to_log)

            return accumulated_content, accumulated_tool_calls # Return all calls for execution

        except KeyboardInterrupt:
            output("info", "\nStreaming interrupted by user.")
            # Log partial message if any
            if accumulated_content or current_tool_call_chunks:
                 # Similar logging logic as above for partial message could be added here
                 pass # For now, just return what we have
            return accumulated_content, accumulated_tool_calls # Return what was gathered
        except Exception as e:
            output("error", f"Error during streaming: {str(e)}")
            import traceback
            output("error", f"Full streaming error details: {traceback.format_exc()}")
            return accumulated_content, accumulated_tool_calls # Return what was gathered

    def _non_stream_response(self, messages, tools):
        """Process a non-streaming response from the API"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=2000,
        )

        if not response.choices: # Safety check
            output("error", "Invalid OpenAI API response: missing choices")
            return "Error: No response from API.", []

        message = response.choices[0].message
        output_text = message.content if message.content else ""

        processed_tool_calls = [] # For execution

        # 1. Structured tool_calls from the message object (OpenAI standard)
        if message.tool_calls:
            for tc_struct in message.tool_calls:
                if tc_struct.type == "function":
                    try:
                        args_str = tc_struct.function.arguments
                        parsed_args = {}
                        if args_str:
                            try:
                                parsed_args = json.loads(args_str)
                            except json.JSONDecodeError:
                                parsed_args = {"raw_arguments": args_str}
                                output("warning", f"Structured tool call arguments for {tc_struct.function.name} not valid JSON: {args_str}")

                        processed_tool_calls.append({
                            "id": tc_struct.id,
                            "name": tc_struct.function.name,
                            "input": parsed_args,
                            "from_text_block": False
                        })
                    except Exception as e:
                        output("error", f"Error processing structured tool call (non-stream): {e}")

        # 2. Extract tool calls from text content (custom apply_patch and JSON)
        if output_text:
            extracted_text_tool_calls = self.extract_tool_calls_from_text(output_text)
            for tc in extracted_text_tool_calls:
                tool_call_id = f"manual_{tc.get('name', 'unknown')}_{uuid.uuid4().hex[:8]}"
                args = tc.get("arguments", {})
                if not isinstance(args, dict):
                     output("warning", f"Text-extracted tool call args not dict (non-stream): {args}. Wrapping.")
                     args = {"value": args}

                processed_tool_calls.append({
                    "id": tool_call_id,
                    "name": tc["name"],
                    "input": args,
                    "from_text_block": True
                })

        # Log the assistant message to history
        assistant_message_to_log = {"role": "assistant"}
        if output_text: # Content always comes first
            assistant_message_to_log["content"] = output_text

        # Include ALL tool calls in the history, both structured and extracted from text
        # This ensures tool responses can be matched with tool calls
        if processed_tool_calls:
            # Explicitly create the tool_calls list first, then assign it to the message
            tool_calls_for_log = []
            for tc in processed_tool_calls:
                tool_call_entry = {
                    "id": tc["id"],
                    "type": "function",  # Assuming all are functions
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["input"])  # Arguments should be stringified JSON
                    }
                }
                tool_calls_for_log.append(tool_call_entry)

            # Now assign the constructed list
            assistant_message_to_log["tool_calls"] = tool_calls_for_log

        if "content" in assistant_message_to_log or "tool_calls" in assistant_message_to_log:
            self.messages.append(assistant_message_to_log)

        return output_text, processed_tool_calls
