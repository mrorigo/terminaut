
## Cursor Rules

Terminaut includes an implementation of Cursor Rules, inspired by the [Cursor editor's rules system](https://docs.cursor.com/context/rules). This allows you to define project-specific guidelines, boilerplate, and domain knowledge that can be automatically applied or manually invoked.

> **Note:** While inspired by Cursor Rules, this implementation has some differences and limitations compared to Cursor's implementation.

### Compatibility with Cursor Rules

#### Supported Features:
- `.cursor/rules/` directory structure for rule discovery
- `.mdc` file format with YAML frontmatter
- `alwaysApply` for rules that should be included in every prompt
- `globs` for auto-attaching rules based on file patterns
- `@file` references to include external files
- Manual rule invocation with `@RuleName` syntax

#### Differences and Limitations:
- **Rule Discovery**: Currently only identifies file paths mentioned in the latest user message
- **AGENT_REQUESTED Rules**: While the rule type is defined, the LLM doesn't proactively request relevant rules
- **Manual Rules**: Any rule that is not an ALWAYS rule can be manually invoked (unlike Cursor's stricter typing)
- **Rule Application**: Rules are consolidated into the system prompt

### Rule Types

- **ALWAYS Rules**: Automatically applied to every conversation
- **AUTO_ATTACHED Rules**: Applied when files matching specified globs are mentioned in the user's input
- **MANUAL Rules**: Any rule that can be explicitly invoked with `@RuleName` syntax (any non-ALWAYS rule)

### Creating Rules

1. Create a `.cursor/rules/` directory in your project
2. Add `.mdc` files with rules (e.g., `.cursor/rules/python.mdc`)

### Rule Format

Rules use the `.mdc` format: YAML frontmatter followed by markdown content:

```md
---
description: "Short description of the rule"
globs: ["*.py", "src/*.js"]  # File patterns for AUTO_ATTACHED rules
alwaysApply: false           # Set true for ALWAYS rules
---

This is the rule content.
Any markdown content goes here.

Reference external files with @file.ext syntax.
```

### Rule Type Determination

- If `alwaysApply: true` → ALWAYS rule (applied to every conversation)
- If `globs` is present and non-empty → AUTO_ATTACHED rule (applied when matching files are mentioned)
- Otherwise → MANUAL rule (can be invoked with @RuleName)

### Using @file References

You can include the content of other files in your rules using the `@file.ext` syntax:

```md
---
description: "Rule with file references"
---

Here's some boilerplate:

@template.py

This will be replaced with the content of template.py
```

Referenced files are resolved relative to the location of the `.mdc` rule file.

### Manually Invoking Rules

Any rule that is not an ALWAYS rule can be manually invoked using the `@RuleName` syntax in your prompt:

```
@python Write a function that calculates Fibonacci sequence
```

When you use `@RuleName`:
1. Terminaut extracts the rule name (without the @ symbol)
2. Searches for a matching rule in the `.cursor/rules/` directories
3. If found, resolves its content (including any @file references)
4. Adds the resolved rule content to the system prompt for that interaction

You can invoke multiple rules in a single prompt: `@python @style Write a sorting function`.

### Examples

**ALWAYS Rule (style guide)**:
```md
---
description: "Project style guide"
alwaysApply: true
---

## Project Style Guide
- Use 4 spaces for indentation
- Use camelCase for variables
- Use PascalCase for classes
```

**AUTO_ATTACHED Rule (Python)**:
```md
---
description: "Python coding standards"
globs: ["*.py"]
---

When writing Python code:
- Use type hints
- Write docstrings for all functions
- Follow PEP 8
```

**MANUAL Rule (template)**:
```md
---
description: "API endpoint template"
---

Here's the standard API endpoint structure:

@endpoint-template.py
```
