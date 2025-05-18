from .output import output

from .output import TAG_STYLES

def user_input():
    # Use the same emoji and color as the output handler for user_input
    style, emoji = TAG_STYLES.get("user_input", ("", ""))
    try:
        # Print the prompt with emoji and tag, and flush to ensure it appears before input
        prompt = f"{style}{emoji}[user]: {''}\033[0m"
        x = input(prompt)
    except KeyboardInterrupt:
        print()
        output("info", "Exiting agent loop. Goodbye!")
        raise SystemExit(0)
    if x.lower() in ["exit", "quit", "/exit", "/quit"]:
        output("info", "Exiting agent loop. Goodbye!")
        raise SystemExit(0)
    return [{"role": "user", "content": x}]
