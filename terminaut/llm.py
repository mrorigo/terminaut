import os
import json
import re
import uuid
import openai

from .output import output
from .tools import bash_function

HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT", "20"))

class LLM:
    def __init__(self, model, base_url=None):
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError("OPENAI_API_KEY environment variable not found.")
        self.model = model
        self.messages = []
        # Load system prompt from file
        try:
            with open("system-prompt.md", "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except Exception as e:
            output("error", f"Failed to read system prompt: {e}")
            self.system_prompt = "You are a helpful AI assistant."
        self.functions = [bash_function]
        self.client = openai.OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=base_url
        ) if base_url else openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def __call__(self, content):
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
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            functions=self.functions,
            function_call="auto",
            max_tokens=2000,
        )
        message = response.choices[0].message
        output_text = ""
        tool_calls = []

        # Helper: parse tool call JSON from text/code block
        def extract_tool_calls_from_text(text):
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

        extracted_tool_calls = []
        if message.content:
            output_text += message.content
            # Try to extract tool calls from text if present
            extracted_tool_calls = extract_tool_calls_from_text(message.content)
            for tc in extracted_tool_calls:
                # Generate a unique id for each tool call
                tool_call_id = f"manual_{uuid.uuid4().hex[:8]}"
                # Arguments may be a dict or a JSON string
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
        # Also handle structured tool_calls
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": tc.function.arguments and json.loads(tc.function.arguments),
                    "from_text_block": False
                })
        # Save assistant message
        if extracted_tool_calls:
            # If tool calls were extracted from text, log them as tool_calls with empty content
            self.messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["input"])
                        }
                    }
                    for tc in tool_calls if tc.get("from_text_block")
                ]
            })
        else:
            # Otherwise, log as before (structured tool_calls or plain content)
            self.messages.append({
                "role": "assistant",
                "content": message.content if message.content else "",
                "tool_calls": getattr(message, "tool_calls", None)
            })
        return output_text, tool_calls