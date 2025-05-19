import os
import json
import re
import uuid
import openai

from .output import output
from .tools import bash_function

HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT", "20"))

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
        # Truncate history to HISTORY_LIMIT (preserve system prompt if present)
        sys_idx = next((i for i, m in enumerate(self.messages) if m.get("role") == "system"), None)
        if sys_idx is not None:
            # Always keep system prompt as first message
            keep = [self.messages[sys_idx]]
            rest = self.messages[:sys_idx] + self.messages[sys_idx+1:]
            if len(rest) > HISTORY_LIMIT - 1:
                rest = rest[-(HISTORY_LIMIT - 1):]
            self.messages = keep + rest
        else:
            if len(self.messages) > HISTORY_LIMIT:
                self.messages = self.messages[-HISTORY_LIMIT:]
        # Insert system prompt if first message
        messages = []
        if not any(m["role"] == "system" for m in self.messages):
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self.messages)
        
        tools = [{"type": "function", "function": func} for func in self.functions]
        
        try:
            if stream:
                return self._stream_response(messages, tools)
            else:
                return self._non_stream_response(messages, tools)
        except Exception as e:
            output("error", f"OpenAI API error: {str(e)}")
            # Print the full exception details for debugging
            import traceback
            output("error", f"Full error details: {traceback.format_exc()}")
            return f"Error calling OpenAI API: {str(e)}", []
            
    def _stream_response(self, messages, tools):
        """Process a streaming response from the API"""
        import time
        from .output import output
        
        # State for accumulating the response
        accumulated_content = ""
        accumulated_tool_calls = []
        tool_call_in_progress = {}
        current_tool_call_chunks = {}
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=2000,
                stream=True,
            )
            
            for chunk in stream:
                # Handle keyboard interrupt during streaming
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Process content updates
                if hasattr(delta, 'content') and delta.content is not None:
                    accumulated_content += delta.content
                    # Print content chunk immediately
                    output("stream", delta.content)
                
                # Process tool_calls updates
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        # Initialize if new tool call
                        if tool_call.index not in current_tool_call_chunks:
                            current_tool_call_chunks[tool_call.index] = {
                                "id": "",
                                "type": "",
                                "function": {"name": "", "arguments": ""}
                            }
                        
                        # Update tool call id
                        if hasattr(tool_call, 'id') and tool_call.id is not None:
                            current_tool_call_chunks[tool_call.index]["id"] += tool_call.id
                        
                        # Update tool call type
                        if hasattr(tool_call, 'type') and tool_call.type is not None:
                            current_tool_call_chunks[tool_call.index]["type"] += tool_call.type
                        
                        # Update function name
                        if (hasattr(tool_call, 'function') and 
                            hasattr(tool_call.function, 'name') and 
                            tool_call.function.name is not None):
                            current_tool_call_chunks[tool_call.index]["function"]["name"] += tool_call.function.name
                        
                        # Update function arguments
                        if (hasattr(tool_call, 'function') and 
                            hasattr(tool_call.function, 'arguments') and 
                            tool_call.function.arguments is not None):
                            current_tool_call_chunks[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
                
                # Check for finish reason
                if chunk.choices[0].finish_reason is not None:
                    break
                    
                # Small delay to prevent UI flicker
                time.sleep(0.01)
            
            # Process completed tool calls
            for index, tc in current_tool_call_chunks.items():
                if tc["id"] and tc["function"]["name"]:
                    try:
                        # Convert arguments string to dictionary
                        args = tc["function"]["arguments"]
                        if args:
                            try:
                                parsed_args = json.loads(args)
                            except:
                                parsed_args = {"raw_arguments": args}
                        else:
                            parsed_args = {}
                            
                        accumulated_tool_calls.append({
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": parsed_args,
                            "from_text_block": False
                        })
                    except Exception as e:
                        output("error", f"Error processing tool call: {e}")
            
            # Search for tool calls in accumulated content
            extracted_tool_calls = self.extract_tool_calls_from_text(accumulated_content)
            for tc in extracted_tool_calls:
                tool_call_id = f"manual_{uuid.uuid4().hex[:8]}"
                args = tc["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                accumulated_tool_calls.append({
                    "id": tool_call_id,
                    "name": tc["name"],
                    "input": args,
                    "from_text_block": True
                })
            
            # Add the completed message to history
            if accumulated_tool_calls:
                tool_calls_for_message = [
                    {
                        "id": tc.get("id", f"unknown_{uuid.uuid4().hex[:8]}"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", "unknown"),
                            "arguments": json.dumps(tc.get("input", {}))
                        }
                    }
                    for tc in accumulated_tool_calls
                ]
                self.messages.append({
                    "role": "assistant",
                    "content": accumulated_content,
                    "tool_calls": tool_calls_for_message
                })
            else:
                self.messages.append({
                    "role": "assistant",
                    "content": accumulated_content,
                })
            
            return accumulated_content, accumulated_tool_calls
            
        except KeyboardInterrupt:
            output("info", "\nStreaming interrupted by user")
            return accumulated_content, accumulated_tool_calls
        except Exception as e:
            output("error", f"Error during streaming: {str(e)}")
            return accumulated_content, accumulated_tool_calls
            
    def extract_tool_calls_from_text(self, text):
        """Helper: parse tool call JSON from text/code block"""
        # Match any code block guard (json, python, tool_call, etc.) or plain ```
        code_block_pattern = re.compile(
            r"```(?:[a-zA-Z0-9_]+)?\s*([\s\S]+?)\s*```", re.IGNORECASE
        )
        matches = code_block_pattern.findall(text)
        candidates = matches if matches else [text]
        tool_calls = []
        for candidate in candidates:
            candidate = candidate.strip()
            # Sometimes the code block may contain extra markdown or comments, try to extract JSON object
            # Remove leading/trailing markdown comments or lines
            candidate = re.sub(r"^<!--.*?-->\s*", "", candidate, flags=re.DOTALL)
            candidate = re.sub(r"\s*<!--.*?-->$", "", candidate, flags=re.DOTALL)
            # Try to parse as JSON object or array
            try:
                obj = json.loads(candidate)
            except Exception:
                # Try to extract the first JSON object in the candidate
                json_obj_pattern = re.compile(r"\{[\s\S]*\}")
                json_match = json_obj_pattern.search(candidate)
                if json_match:
                    try:
                        obj = json.loads(json_match.group(0))
                    except Exception:
                        continue
                else:
                    continue
            # Accept both list and single object
            objs = obj if isinstance(obj, list) else [obj]
            for o in objs:
                # Accept OpenAI tool_call format
                if (
                    isinstance(o, dict)
                    and "function" in o
                    and isinstance(o["function"], dict)
                    and "name" in o["function"]
                    and "arguments" in o["function"]
                ):
                    args = o["function"]["arguments"]
                    # Accept both dict and list for arguments, and also stringified JSON
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            pass
                    tool_calls.append({
                        "name": o["function"]["name"],
                        "arguments": args
                    })
                # Accept simple {"name": ..., "arguments": ...}
                elif (
                    isinstance(o, dict)
                    and "name" in o
                    and "arguments" in o
                ):
                    args = o["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            pass
                    tool_calls.append({
                        "name": o["name"],
                        "arguments": args
                    })
        # Try to find a JSON object in the text if nothing found
        if not tool_calls:
            json_obj_pattern = re.compile(r"\{[\s\S]*?\}")
            for match in json_obj_pattern.findall(text):
                try:
                    o = json.loads(match)
                    if (
                        isinstance(o, dict)
                        and "function" in o
                        and isinstance(o["function"], dict)
                        and "name" in o["function"]
                        and "arguments" in o["function"]
                    ):
                        args = o["function"]["arguments"]
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        tool_calls.append({
                            "name": o["function"]["name"],
                            "arguments": args
                        })
                    elif (
                        isinstance(o, dict)
                        and "name" in o
                        and "arguments" in o
                    ):
                        args = o["arguments"]
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        tool_calls.append({
                            "name": o["name"],
                            "arguments": args
                        })
                except Exception:
                    continue
        return tool_calls
    
    def _non_stream_response(self, messages, tools):
        """Process a non-streaming response from the API"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=2000,
        )
        
        # Safety check for response structure
        if not hasattr(response, 'choices') or len(response.choices) == 0:
            output("error", "Invalid OpenAI API response: missing or empty choices")
            return "I received an error from the server. Please try again.", []

        message = response.choices[0].message

        # Initialize variables for processing the response
        output_text = ""
        tool_calls = []

        # --- 1. Collect all tool calls from all sources ---
        tool_calls = []
        extracted_tool_calls = []

        # (A) Content-inlined tool calls (code blocks, JSON, etc.)
        if message.content:
            output_text += message.content
            extracted_tool_calls = self.extract_tool_calls_from_text(message.content)
            for tc in extracted_tool_calls:
                tool_call_id = f"manual_{uuid.uuid4().hex[:8]}"
                args = tc["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                tool_calls.append({
                    "id": tool_call_id,
                    "name": tc["name"],
                    "input": args,
                    "from_text_block": True
                })

        # (B) Structured tool_calls (OpenAI v2+)
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": tc.function.arguments and json.loads(tc.function.arguments),
                    "from_text_block": False
                })

        # (C) Single function_call (OpenAI v1)
        if hasattr(message, "function_call") and message.function_call:
            fc = message.function_call
            # Use a unique id for this function call
            tool_call_id = f"function_{uuid.uuid4().hex[:8]}"
            args = fc.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            tool_calls.append({
                "id": tool_call_id,
                "name": fc.name,
                "input": args,
                "from_text_block": False
            })

        # --- 2. Log assistant message with correct OpenAI tool_calls structure ---
        # If any tool calls were extracted from content, log only those as tool_calls
        if tool_calls and any(tc is not None and isinstance(tc, dict) and tc.get("from_text_block") for tc in tool_calls):
            tool_calls_for_message = [
                {
                    "id": tc.get("id", f"unknown_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", "unknown"),
                        "arguments": json.dumps(tc.get("input", {}))
                    }
                }
                for tc in tool_calls if tc is not None and isinstance(tc, dict) and tc.get("from_text_block")
            ]
            tool_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": tool_calls_for_message
            }
            self.messages.append(tool_message)
        # Otherwise, if there are structured tool_calls or function_call, log those
        elif tool_calls:
            tool_calls_for_message = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["input"])
                    }
                }
                for tc in tool_calls
            ]
            tool_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": tool_calls_for_message
            }
            # print("[DEBUG] Assistant message with tool_calls to be appended:", tool_message)
            self.messages.append(tool_message)
        else:
            # No tool calls, just log the content
            tool_message = {
                "role": "assistant",
                "content": message.content if message.content else "",
            }
            self.messages.append(tool_message)

        return output_text, tool_calls
