import os
import json
import uuid
import openai
from terminaut.llm.prompt import SystemPromptConstructor
from terminaut.llm.tool_parser import ToolCallParser
from terminaut.rules.manager import RuleManager

from .history import MessageHistory

from terminaut.output import output
from terminaut.tools import bash_function
from terminaut.tools.apply_patch import apply_patch_function

from typing import Optional, List, Dict, Any, Tuple

# Constants
HISTORY_LIMIT = max(3, int(os.environ.get("HISTORY_LIMIT", "20")))
DEFAULT_MAX_TOKENS = 20000 # Consider making this configurable

class OpenAICaller:
    """Handles direct interaction with the OpenAI API."""
    def __init__(self, client: openai.OpenAI, model: str, functions: List[Dict[str, Any]]):
        self._client = client
        self._model = model
        # Translate tool function dicts into the list format expected by the API create call
        self._tools = [{"type": "function", "function": func} for func in functions] if functions else None

    def call_api(self, messages: List[Dict[str, Any]], stream: bool = True, max_tokens: int = DEFAULT_MAX_TOKENS):
        """
        Makes the API call to OpenAI chat completions.
        Returns the stream iterator if stream=True, otherwise returns the response object.
        Handles basic API exceptions.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=self._tools,
                tool_choice="auto" if self._tools else "none", # Use tools if provided
                max_tokens=max_tokens,
                stream=stream,
            )
            return response
        except openai.APIError as e:
            output("error", f"OpenAI API error: {e.status_code} - {e.response.text}")
            raise # Re-raise to be caught by the main loop if necessary
        except Exception as e:
            output("error", f"An unexpected API call error occurred: {str(e)}")
            import traceback
            output("error", f"Full error details: {traceback.format_exc()}")
            raise # Re-raise

class LLM:
    """
    Orchestrates the LLM interaction, managing history, system prompt,
    API calls, and tool call processing.
    """
    # Track manually invoked rules for this LLM instance
    manual_rule_names: List[str] = [] # This feels a bit odd as a class variable,
                                       # maybe better on instance? User might interact
                                       # with multiple LLMs? Assuming one LLM instance per session.
                                       # Keep as instance variable for now.

    def __init__(self, model: str, base_url: Optional[str] = None, system_prompt: Optional[str] = None, rule_manager: Optional[RuleManager] = None):
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError("OPENAI_API_KEY environment variable not found.")

        self.model = model
        self.rule_manager = rule_manager

        # Initialize helper components
        self.history = MessageHistory(HISTORY_LIMIT)
        self.text_parser = ToolCallParser() # Parses tool calls embedded in text output

        # Use provided system prompt, or load from file, or fallback to default
        base_system_prompt_content = system_prompt
        if base_system_prompt_content is None:
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../", "system-prompt.md")
            local_path = os.path.abspath(local_path)
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    base_system_prompt_content = f.read()
            except Exception as e:
                output("error", f"Failed to read system prompt: {e}")
                base_system_prompt_content = "You are a helpful AI assistant."

        self.prompt_constructor = SystemPromptConstructor(base_system_prompt_content, self.rule_manager)

        # Hardcoded tools for now
        self.available_functions = [bash_function, apply_patch_function]
        self.api_caller = OpenAICaller(
            client=openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url) if base_url else openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"]),
            model=self.model,
            functions=self.available_functions
        )

        # Instance-specific manual rule names
        self.manual_rule_names = []


    def __call__(self, content: List[Dict[str, Any]], stream: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Processes input messages, calls the LLM API, handles response (streaming or not),
        extracts tool calls, manages history, and returns output content and tool calls for execution.

        Args:
            content: A list of message dictionaries (e.g., user input, tool results).
            stream: Whether to stream the response.

        Returns:
            A tuple containing:
            - The accumulated text content from the LLM response.
            - A list of unified tool call dictionaries for execution.
        """
        # IMPORTANT: Save the current content *before* adding to history for context file extraction
        current_input_messages = content.copy() if content else []

        # Add incoming messages (user input, tool results) to history
        self.history.add_messages(content)

        # --- Dynamically build the system prompt for this call ---
        # This requires the rule manager and potentially active files from the *current* user input
        system_prompt_content = self.prompt_constructor.build_system_prompt(
             current_input_messages, self.manual_rule_names
        )

        # Clear old system messages and insert the new one
        self.history.clear_system_messages()
        self.history.insert_system_message(system_prompt_content)

        # Get messages for the API call (truncated history)
        api_call_messages = self.history.get_truncated_history()

        # Assert that the first message is the system message after history prep
        assert api_call_messages[0].get("role") == "system", "The first message for the API call must always have the role 'system'."

        # output("info_detail", f"Messages sent to API: {json.dumps(api_call_messages, indent=2)}") # Excessive logging

        accumulated_content = ""
        structured_tool_calls_from_api: List[Dict[str, Any]] = [] # Tool calls from API response objects (structured)

        try:
            api_response = self.api_caller.call_api(api_call_messages, stream=stream, max_tokens=DEFAULT_MAX_TOKENS)

            if stream:
                current_tool_call_chunks: Dict[int, Dict[str, Any]] = {} # For assembling tool_calls from stream chunks
                chunk_count = 0
                for chunk in api_response: # api_response is the stream iterator
                    chunk_count += 1

                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    # Accumulate and display content
                    if hasattr(delta, 'content') and delta.content is not None:
                        accumulated_content += delta.content
                        output("stream", delta.content) # Stream content out immediately

                    # Accumulate structured tool call chunks
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
                            if tool_call_chunk.function:
                                if tool_call_chunk.function.name:
                                    tc_data["function"]["name"] += tool_call_chunk.function.name
                                if tool_call_chunk.function.arguments:
                                    tc_data["function"]["arguments"] += tool_call_chunk.function.arguments

                    if chunk.choices[0].finish_reason is not None:
                        # Stream finished or stopped
                        break

                    # time.sleep(0.01) # Small delay, might not be necessary

                # Process fully assembled structured tool calls from chunks
                for _index, tc_chunk_data in current_tool_call_chunks.items():
                    if tc_chunk_data.get("id") and tc_chunk_data["function"].get("name"):
                        try:
                            args_str = tc_chunk_data["function"]["arguments"]
                            parsed_args = {} # Default to empty dict
                            if args_str:
                                try:
                                    parsed_args = json.loads(args_str)
                                except json.JSONDecodeError:
                                    # If args are not valid JSON, pass as raw string under a specific key
                                    parsed_args = {"raw_arguments": args_str}
                                    # output("warning", f"Structured tool call arguments for {tc_chunk_data['function']['name']} not valid JSON: {args_str}") # Excessive logging

                            # Ensure arguments is a dict
                            if not isinstance(parsed_args, dict):
                                output("warning", f"Structured tool call arguments not dict after parsing ({tc_chunk_data['function'].get('name')}), was {type(parsed_args)}. Wrapping.")
                                parsed_args = {"value": parsed_args} # Wrap non-dict args

                            structured_tool_calls_from_api.append({
                                "id": tc_chunk_data["id"],
                                "name": tc_chunk_data["function"]["name"],
                                "input": parsed_args, # This is the dict of arguments
                                "from_text_block": False # Indicates it's a structured tool call
                            })
                        except Exception as e:
                            output("error", f"Error processing structured tool call chunk: {e}")

            else: # Non-streaming response
                response_message = api_response.choices[0].message
                accumulated_content = response_message.content if response_message.content else ""

                # Extract structured tool_calls from the message object
                if response_message.tool_calls:
                    for tc_struct in response_message.tool_calls:
                        if tc_struct.type == "function":
                            try:
                                args_str = tc_struct.function.arguments
                                parsed_args = {} # Default to empty dict
                                if args_str:
                                    try:
                                        parsed_args = json.loads(args_str)
                                    except json.JSONDecodeError:
                                        parsed_args = {"raw_arguments": args_str}
                                        # output("warning", f"Structured tool call arguments for {tc_struct.function.name} not valid JSON: {args_str}") # Excessive logging

                                # Ensure arguments is a dict
                                if not isinstance(parsed_args, dict):
                                    output("warning", f"Structured tool call args not dict after parsing ({tc_struct.function.name}), was {type(parsed_args)}. Wrapping.")
                                    parsed_args = {"value": parsed_args} # Wrap non-dict args

                                structured_tool_calls_from_api.append({
                                    "id": tc_struct.id,
                                    "name": tc_struct.function.name,
                                    "input": parsed_args,
                                    "from_text_block": False
                                })
                            except Exception as e:
                                output("error", f"Error processing structured tool call (non-stream): {e}")

        except Exception:
            # api_caller already logged the error, just return partial state
            return accumulated_content, structured_tool_calls_from_api # Return what was gathered before error

        # --- Post-API call processing ---

        # Extract tool calls from the accumulated text content (custom apply_patch and JSON)
        extracted_text_tool_calls = self.text_parser.extract_tool_calls_from_text(accumulated_content)

        # Combine structured tool calls and text-extracted tool calls
        unified_tool_calls: List[Dict[str, Any]] = list(structured_tool_calls_from_api) # Start with structured calls

        # Add text-extracted calls, assigning unique IDs and ensuring dict arguments
        for tc in extracted_text_tool_calls:
            # Generate a unique ID for text-extracted calls if none exists
            tool_call_id = f"manual_{tc.get('name', 'unknown')}_{uuid.uuid4().hex[:8]}"

            # Ensure arguments is a dict
            args = tc.get("arguments", {})
            if not isinstance(args, dict):
                 output("warning", f"Text-extracted tool call args not dict, was {type(args)}. Wrapping.")
                 args = {"value": args} # Wrap non-dict args

            unified_tool_calls.append({
                "id": tool_call_id,
                "name": tc["name"],
                "input": args,
                "from_text_block": True # Indicate this was extracted from text
            })

        # Add the assistant's response message to history
        # This needs to be structured correctly for OpenAI's history format
        assistant_message_to_log: Dict[str, Any] = {"role": "assistant"}
        if accumulated_content:
            assistant_message_to_log["content"] = accumulated_content

        # Include ALL tool calls (structured and text-extracted) in the history log
        # The arguments need to be stringified JSON in the history message,
        # even if the 'input' field in the unified_tool_calls list is a dict/raw string.
        if unified_tool_calls:
             tool_calls_for_log = []
             for tc in unified_tool_calls:
                  # Arguments for the log must be a JSON string of the input dict
                  args_for_log = json.dumps(tc.get("input", {}))
                  tool_calls_for_log.append({
                       "id": tc["id"],
                       "type": "function",  # Assuming all are functions
                       "function": {
                            "name": tc["name"],
                            "arguments": args_for_log
                       }
                  })
             assistant_message_to_log["tool_calls"] = tool_calls_for_log


        # Only add message if it has content or tool calls
        if "content" in assistant_message_to_log or "tool_calls" in assistant_message_to_log:
             self.history.add_message(assistant_message_to_log)
        else:
             output("warning", "LLM response had no content or tool_calls!")


        # Return the content and the unified list of tool calls for execution
        # The tool calls returned here have the parsed 'input' (dict or raw value)
        # which is ready for handle_tool_call.
        return accumulated_content, unified_tool_calls
