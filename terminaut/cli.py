import os
from .llm import LLM
from .tools import handle_tool_call
from .input import user_input
from .output import output

def loop(llm, initial_prompt=None):
    msg = [{"role": "user", "content": initial_prompt}] if initial_prompt else user_input()
    while True:
        output_text, tool_calls = llm(msg)
        if output_text.strip():
            output("agent", output_text)
        # If there are tool calls, handle them and immediately call LLM again with the tool result(s)
        while tool_calls:
            msg = [handle_tool_call(tc) for tc in tool_calls]
            output_text, tool_calls = llm(msg)
            if output_text.strip():
                output("agent", output_text)
        # Only prompt user when there are no tool calls left
        msg = user_input()

import argparse

def main():
    parser = argparse.ArgumentParser(description="Terminaut: LLM Agent Loop with OpenAI Chat Completions API and Bash Tool")
    parser.add_argument("--system-prompt", type=str, help="Path to the system prompt file")
    parser.add_argument("--first-prompt", type=str, help="Initial user prompt (string or file path)")
    args = parser.parse_args()

    # Read system prompt from file if specified
    system_prompt = None
    if args.system_prompt:
        try:
            with open(args.system_prompt, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except Exception as e:
            output("error", f"Failed to read system prompt from {args.system_prompt}: {e}")
            return

    # Read first user prompt from file or use as string
    first_prompt = None
    if args.first_prompt:
        try:
            if os.path.isfile(args.first_prompt):
                with open(args.first_prompt, "r", encoding="utf-8") as f:
                    first_prompt = f.read().strip()
            else:
                first_prompt = args.first_prompt.strip()
        except Exception as e:
            output("error", f"Failed to read first prompt: {e}")
            return

    try:
        output("info", "=== Terminaut: LLM Agent Loop with OpenAI Chat Completions API and Bash Tool ===")
        output("info", "Type '/exit' to end the conversation.")
        llm = LLM(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            system_prompt=system_prompt
        )
        if first_prompt:
            loop(llm, initial_prompt=first_prompt)
        else:
            loop(llm)
    except KeyboardInterrupt:
        output("info", "Exiting. Goodbye!")
    except Exception as e:
        output("error", f"An error occurred: {str(e)}")
