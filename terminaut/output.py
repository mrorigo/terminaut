import sys
from colorama import init, Fore, Style

init()

TAG_STYLES = {
    "info":      (Fore.CYAN + Style.BRIGHT, "ℹ️"),
    "info_detail":      (Fore.CYAN, " "),
    "user_input":(Fore.BLUE + Style.BRIGHT, "👤"),
    "agent":     (Fore.MAGENTA + Style.BRIGHT, "🤖"),
    "stream":    (Fore.MAGENTA + Style.NORMAL, ""),  # For streaming content (no emoji)
    "bash_command": (Fore.YELLOW + Style.BRIGHT, "💻"),
    "bash_output":  (Fore.GREEN + Style.NORMAL, "📤"),
    "approval_prompt": (Fore.YELLOW + Style.BRIGHT, "❓"),
    "approval_response": (Fore.CYAN + Style.NORMAL, "➡️"),
    "error":     (Fore.RED + Style.BRIGHT, "❌"),
    "tool_call": (Fore.CYAN + Style.BRIGHT, "🛠️"),
    "summary":   (Fore.GREEN + Style.BRIGHT, "✅"),
    "warning":   (Fore.YELLOW + Style.BRIGHT, "⚠️"),
    "default":   (Fore.WHITE + Style.NORMAL, "•"),
}

def output(tag: str, message: str, streaming: bool = False):
    """Central output handler for all script output, with color and emoji."""
    style, emoji = TAG_STYLES.get(tag, TAG_STYLES["default"])

    # Handle streaming mode
    if tag == "stream" or streaming:
        print(f"{style}{message}{Style.RESET_ALL}", end="", flush=True)
        return

    if tag == "info_detail":
        tag = "info"

    # Standard multi-line messages: prefix only the first line with emoji, indent others
    lines = message.splitlines() or [""]
    if lines:
        print(f"{style}{emoji}[{tag}]{Style.RESET_ALL} {lines[0]}")
        for line in lines[1:]:
            print(f"{style}   {line}{Style.RESET_ALL}")
    else:
        print(f"{style}{emoji}[{tag}]{Style.RESET_ALL}")

    sys.stdout.flush()
