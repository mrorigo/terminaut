from .output import output, TAG_STYLES
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

def user_multiline_input(prompt_html):
    session = PromptSession()
    try:
        text = session.prompt(
            HTML(prompt_html),
            multiline=True,
            bottom_toolbar=HTML(
                '<style fg="ansiyellow">[Type message. Enter = newline, Esc+Enter or F2 = submit]</style>'
            )
        )
        return text
    except KeyboardInterrupt:
        print()
        output("info", "Exiting agent loop. Goodbye!")
        raise SystemExit(0)

def user_input():
    # Map colorama style to prompt_toolkit HTML style
    color = "ansiblue"
    emoji = TAG_STYLES.get("user_input", ("", "👤"))[1]
    prompt_html = f'<b fg="{color}">{emoji}[user]: </b>'
    x = user_multiline_input(prompt_html)
    if x.strip().lower() in ["exit", "quit", "/exit", "/quit"]:
        output("info", "Exiting agent loop. Goodbye!")
        raise SystemExit(0)
    return [{"role": "user", "content": x}]
