# Terminaut

**Explore your codebase. Command with confidence.**

Terminaut is a terminal-based, agentic coding assistant that brings the power of modern LLMs to your local development workflow. It enables natural language interaction with your codebase, safe shell command execution, patch application, and more—all from your terminal.

---

## Features

- **Agentic CLI Coding Assistant**  
  Terminaut wraps OpenAI-compatible models (OpenAI, Ollama, OpenRouter, etc.) to provide a conversational, agentic interface for coding tasks.

- **Tool Calling & Shell Integration**  
  The agent can call shell commands, read files, and apply patches using a robust tool-calling interface.

- **Patch Application**  
  Unified diff patches are applied via a standalone `apply_patch` script, ensuring safe and auditable code changes.

- **User Approval for Shell Commands**  
  All shell commands require explicit user approval before execution, keeping you in control.

- **Robust Tool Call Parsing**  
  Terminaut detects tool calls in both structured API responses and as JSON/code blocks in LLM text, tolerant to various code block guards and formatting.

- **History Management**  
  Configurable message history limit (default: 20) to keep context efficient and avoid runaway context windows.

- **Tagged Output Logging**  
  All output is tagged by context (agent, user_input, bash_command, etc.) for easy parsing, UI integration, or telemetry.

- **Provider Agnostic**  
  Works with OpenAI, Ollama, OpenRouter, and any OpenAI-compatible API.

- **Extensible Architecture**  
  Modular Python package structure for easy extension and maintenance.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/terminaut.git
   cd terminaut
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Or use [uv](https://github.com/astral-sh/uv) for fast installs:
   ```bash
   uv pip install -r requirements.txt
   ```

3. **Make sure `apply_patch` is executable:**
   ```bash
   chmod +x apply_patch
   ```

---

## Usage

### With Ollama

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1/
export OPENAI_API_KEY=dummy
export OPENAI_MODEL=qwen3:14b-q8_0
python main.py
```

### With OpenAI

```bash
export OPENAI_BASE_URL=https://api.openai.com/v1/
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=o4-mini
python main.py
```

### General

- **Start the agent:**
  ```bash
  python main.py
  ```
- **Type your requests at the prompt.**
- **Approve or deny shell commands as prompted.**
- **Type `exit` or `quit` to leave.**

---

## Configuration

| Variable           | Description                                      | Default         |
|--------------------|--------------------------------------------------|-----------------|
| `OPENAI_BASE_URL`  | Base URL for OpenAI-compatible API               | (required)      |
| `OPENAI_API_KEY`   | API key for the LLM provider                     | (required)      |
| `OPENAI_MODEL`     | Model name (e.g., `gpt-4o`, `qwen3:14b-q8_0`)    | `gpt-4o`        |
| `HISTORY_LIMIT`    | Max messages to keep in context                  | `20`            |

---

## How It Works

1. **Conversational Loop:**  
   - User enters a prompt.
   - LLM responds, possibly with tool calls (e.g., shell commands).
   - Tool calls are parsed from both structured API responses and code/text blocks.
   - User is prompted to approve shell commands.
   - Tool results are fed back to the LLM for further reasoning.
   - The loop continues until the task is complete.

2. **Patch Application:**  
   - The agent emits unified diff patches.
   - Patches are applied via the `apply_patch` script, which is always invoked with an absolute path for reliability.

3. **History Management:**  
   - Only the most recent N messages are kept in context (configurable).
   - The system prompt is always preserved.

4. **Output Tagging:**  
   - All output is tagged for easy parsing and UI integration.

---

## Architecture

```
terminaut/
  __init__.py
  cli.py         # CLI entrypoint and agent loop
  llm.py         # LLM interface and tool call parsing
  tools.py       # Tool definitions and execution logic
  input.py       # User input handling
  output.py      # Output handler
apply_patch      # Standalone patch application script
main.py          # Entrypoint (calls terminaut.cli.main)
system-prompt.md # System prompt for the agent
```

- **Easily extendable:** Add new tools by defining them in `tools.py` and registering with the LLM.
- **Provider-agnostic:** Works with any OpenAI-compatible API.

---

## Example Session

```
[info] === Terminaut: LLM Agent Loop with OpenAI Chat Completions API and Bash Tool ===
[info] Type 'exit' to end the conversation.
[user_input] Awaiting user input...
You: List all Python files
[agent] {
  "id": "tool_call_1",
  "type": "function",
  "function": {
    "name": "bash",
    "arguments": "{\"command\": \"ls *.py\"}"
  }
}
[bash_command] Approval required for bash command: ls *.py
[approval_prompt] Approve execution of: ls *.py? [y/N]:
Approve execution of this bash command? [y/N]: y
[approval_response] y
[bash_command] User approved execution of: ls *.py
[bash_output] STDOUT:
main.py
cli.py
llm.py
tools.py
input.py
output.py

STDERR:

EXIT CODE: 0
[agent] The Python files in this directory are: main.py, cli.py, llm.py, tools.py, input.py, output.py.
```

---

## Troubleshooting & FAQ

- **Q: `apply_patch` not found?**  
  A: Ensure `apply_patch` is present, executable, and in the repo root. The agent will use its absolute path.

- **Q: How do I use a different model/provider?**  
  A: Set `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` as shown above.

- **Q: Can I add new tools?**  
  A: Yes! Add your tool in `tools.py` and register it in `llm.py`.

- **Q: Why does the agent ask for approval for every shell command?**  
  A: For safety. You can always deny commands you don't trust.

- **Q: How do I change the history limit?**  
  A: Set the `HISTORY_LIMIT` environment variable.

---

## Contributing

Pull requests and issues are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE)

---

**Terminaut** — Your terminal, your mission.