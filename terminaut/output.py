import sys

try:
    from colorama import init, Fore, Style
except ImportError:
    # fallback: no color
    class Dummy:
        RESET_ALL = ''
        BRIGHT = ''
        DIM = ''
        NORMAL = ''
    class DummyFore(Dummy):
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''
    init = lambda: None
    Fore = DummyFore()
    Style = Dummy()

init(autoreset=True)

TAG_STYLES = {
    "info":      (Fore.CYAN + Style.BRIGHT, "ℹ️ "),
    "user_input":(Fore.BLUE + Style.BRIGHT, "👤 "),
    "agent":     (Fore.MAGENTA + Style.BRIGHT, "🤖 "),
    "bash_command": (Fore.YELLOW + Style.BRIGHT, "💻 "),
    "bash_output":  (Fore.GREEN + Style.NORMAL, "📤 "),
    "approval_prompt": (Fore.YELLOW + Style.BRIGHT, "❓ "),
    "approval_response": (Fore.CYAN + Style.NORMAL, "➡️ "),
    "error":     (Fore.RED + Style.BRIGHT, "❌ "),
    "tool_call": (Fore.CYAN + Style.BRIGHT, "🛠️ "),
    "summary":   (Fore.GREEN + Style.BRIGHT, "✅ "),
    "warning":   (Fore.YELLOW + Style.BRIGHT, "⚠️ "),
    "default":   (Fore.WHITE + Style.NORMAL, "• "),
}

def output(tag: str, message: str):
    """Central output handler for all script output, with color and emoji."""
    style, emoji = TAG_STYLES.get(tag, TAG_STYLES["default"])
    # Multi-line messages: prefix only the first line with emoji, indent others
    lines = message.splitlines() or [""]
    if lines:
        print(f"{style}{emoji}[{tag}]{Style.RESET_ALL} {lines[0]}")
        for line in lines[1:]:
            print(f"{style}   {line}{Style.RESET_ALL}")
    else:
        print(f"{style}{emoji}[{tag}]{Style.RESET_ALL}")

    sys.stdout.flush()