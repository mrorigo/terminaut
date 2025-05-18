import os
from .llm import LLM
from .tools import handle_tool_call
from .input import user_input
from .output import output

def loop(llm):
    msg = user_input()
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

def main():
    try:
        output("info", "=== Terminaut: LLM Agent Loop with OpenAI Chat Completions API and Bash Tool ===")
        output("info", "Type '/exit' to end the conversation.")
        loop(LLM(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            base_url=os.environ.get("OPENAI_BASE_URL")
        ))
    except KeyboardInterrupt:
        output("info", "Exiting. Goodbye!")
    except Exception as e:
        output("error", f"An error occurred: {str(e)}")
