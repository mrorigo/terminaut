# Terminaut

**Your terminal, your mission.**

Terminaut is a terminal-based, agentic assistant that brings the power of modern LLMs to your local workflow. While it excels as a coding assistant, Terminaut is much more than that. By customizing the system prompt, you can transform it into a versatile agent for system administration, data analysis, automation, or any task that can be accomplished with Bash commands. Terminaut adapts to your needs, making it the ultimate tool for your terminal.

---

## Features
## Examples of Use Cases

Terminaut's flexibility allows it to handle a wide range of tasks beyond coding. Here are some examples:

- **System Administration**  
  Use Terminaut to manage servers, monitor processes, or automate routine tasks. For example:
  ```bash
  tt --system-prompt sysadmin-prompt.md --first-prompt "Check disk usage and list the top 5 largest files."
  ```

- **Data Analysis**  
  Process and analyze data directly from the terminal. For example:
  ```bash
  tt --system-prompt data-analysis-prompt.md --first-prompt "Summarize the contents of data.csv and calculate the average of column B."
  ```

- **Automation**  
  Automate repetitive tasks by defining workflows in the system prompt. For example:
  ```bash
  tt --system-prompt automation-prompt.md --first-prompt "Backup all .txt files in this directory to /backup."
  ```

These are just a few examples. With a custom system prompt, Terminaut can be tailored to fit virtually any workflow.

- **Agentic CLI Assistant**
  Terminaut wraps OpenAI-compatible models (OpenAI, Ollama, OpenRouter, etc.) to provide a conversational, agentic interface for any task. Whether you're coding, managing systems, or automating workflows, Terminaut adapts to your needs.

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
   git clone https://github.com/mrorigo/terminaut.git
   cd terminaut
   ```

2. **Make sure `apply_patch` is executable:**
   ```bash
   chmod +x apply_patch
   ```

---

## Setting Up a 'tt' Alias

To make it easier to run Terminaut, set up a `tt` alias that points to the `main.py` file in the repository. This allows you to invoke the tool with a short and convenient command.

### Steps to Set Up the Alias

1. **Ensure the `main.py` file is executable:**
   ```bash
   chmod +x /path/to/terminaut/main.py
   ```

2. **Create the alias:**
   Add the following line to your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.bash_profile`):
   ```bash
   alias tt='/path/to/terminaut/main.py'
   ```

   Replace `/path/to/terminaut/main.py` with the absolute path to the `main.py` file in your Terminaut repository.

3. **Reload your shell configuration:**
   After editing your shell configuration file, reload it to apply the changes:
   ```bash
   source ~/.bashrc  # For Bash
   source ~/.zshrc   # For Zsh
   ```

4. **Test the alias:**
   Run the following command to ensure the alias works:
   ```bash
   tt --help
   ```

   If everything is set up correctly, you should see the help output for Terminaut.

### Notes

- The alias will only work in the shell where it is configured. To make it available in all sessions, ensure you add it to your shell's configuration file.
- If you move the Terminaut repository to a different location, update the alias in your shell configuration file to reflect the new path.

---

## Usage

### With Ollama

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1/
export OPENAI_API_KEY=dummy
export OPENAI_MODEL=qwen3:14b-q8_0
tt
```

### With OpenAI

```bash
export OPENAI_BASE_URL=https://api.openai.com/v1/
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=o4-mini
tt
```

### General

- **Start the agent:**
  ```bash
  tt
  ```
- **Specify a custom system prompt file (optional):**
  ```bash
  tt --system-prompt path/to/system-prompt.md
  ```
  *Note:* The system prompt defines the agent's behavior. By customizing it, you can transform Terminaut into a specialized assistant for any task, from coding to system administration or data analysis.
  - **Specify a custom system prompt file (optional):**
    ```bash
    tt --system-prompt path/to/system-prompt.md
    ```
  
    > **Note:** The system prompt defines the agent's behavior. Craft your system prompts carefully for best results—clear instructions and boundaries are important.  
    > See the provided [`system-prompt.md`](system-prompt.md) in this repository for a solid example and starting point.

- **Provide an initial user prompt (optional):**
  ```bash
  tt --first-prompt "List all Python files in this directory."
  ```
  Alternatively, you can provide a file containing the first user prompt:
  ```bash
  tt --first-prompt path/to/first-prompt.txt
  ```
  If a file path is provided, the contents of the file will be used as the first user prompt.

- **Type your requests at the prompt.**
- **Approve or deny shell commands as prompted.**
- **Type `exit` or `quit` to leave.**

---

## Configuration

| Variable/Option    | Description                                      | Default         |
|--------------------|--------------------------------------------------|-----------------|
| `OPENAI_BASE_URL`  | Base URL for OpenAI-compatible API               | (required)      |
| `OPENAI_API_KEY`   | API key for the LLM provider                     | (required)      |
| `OPENAI_MODEL`     | Model name (e.g., `gpt-4o`, `qwen3:14b-q8_0`)    | `gpt-4o`        |
| `HISTORY_LIMIT`    | Max messages to keep in context                  | `20`            |
| `--system-prompt`  | Path to a custom system prompt file              | Default system prompt |
| `--first-prompt`   | Initial user prompt (string or file path)        | None            |

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

### Using Default Options
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

### Using `--system-prompt` and `--first-prompt`
```
$ tt --system-prompt custom-system-prompt.md --first-prompt "List all Python files in this directory."
[info] === Terminaut: LLM Agent Loop with OpenAI Chat Completions API and Bash Tool ===
[info] Type 'exit' to end the conversation.
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
