import os
from .llm import LLM
from .tools import handle_tool_call
from .input import user_input
from .output import output, TAG_STYLES, Style

def loop(llm, initial_prompt=None):
    msg = [{"role": "user", "content": initial_prompt}] if initial_prompt else user_input()
    while True:
        # Print agent marker before streaming begins
        print(f"{TAG_STYLES['agent'][0]}{TAG_STYLES['agent'][1]}[agent]{Style.RESET_ALL} ", end="", flush=True)
        
        # Get streaming response from LLM
        output_text, tool_calls = llm(msg, stream=True)
        
        # Ensure a new line after streaming content
        print()
        
        # Process tool calls regardless of whether there's output text
        # If there are tool calls, handle them and immediately call LLM again with the tool result(s)
        while tool_calls:
            try:
                # Handle each tool call and collect responses
                msg = []
                for tc in tool_calls:
                    if tc is not None:
                        result = handle_tool_call(tc)
                        if result is not None:
                            msg.append(result)
                
                if not msg:  # If no valid tool responses, exit the loop
                    output("error", "No valid tool responses, stopping tool call loop")
                    tool_calls = []
                    continue
                
                # Print agent marker before streaming begins
                print(f"{TAG_STYLES['agent'][0]}{TAG_STYLES['agent'][1]}[agent]{Style.RESET_ALL} ", end="", flush=True)
                
                # Get streaming response for tool call result
                output_text, new_tool_calls = llm(msg, stream=True)
                
                # Ensure a new line after streaming content
                print()
                
                tool_calls = new_tool_calls  # Update tool_calls for next loop iteration
            except Exception as e:
                output("error", f"Error in tool call loop: {str(e)}")
                tool_calls = []  # Stop the loop on error
                
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
