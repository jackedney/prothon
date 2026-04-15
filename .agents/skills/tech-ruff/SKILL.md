---
name: tech-ruff
description: Reference guide for Ruff -- extremely fast Python linter and formatter
user-invocable: false
---

# Ruff

> Purpose: Linting and formatting for all Python code (R4: scaffolded toolchain; enforces code quality via pre-commit hooks and CI)
> Docs: https://docs.astral.sh/ruff/
> Version researched: latest (sourced from Context7). Written in Rust, 10-100x faster than Flake8/Black.

## Quick Start

```bash
# Lint
ruff check src/ tests/

# Lint and auto-fix
ruff check --fix src/ tests/

# Format (Black-compatible)
ruff format src/ tests/

# Format check (no changes, exit 1 if needed)
ruff format --check src/ tests/
```

In this project, all checks run via `uv run poe check` and are enforced by pre-commit hooks.

## Common Patterns

### Configuration in pyproject.toml

```toml
[tool.ruff]
line-length = 88
indent-width = 4
target-version = "py311"

[tool.ruff.lint]
# Enable rule sets: Pyflakes (F), pycodestyle (E), bugbear (B), isort (I)
select = ["E4", "E7", "E9", "F", "B", "I"]
ignore = []

# Allow autofix for all enabled rules
fixable = ["ALL"]
unfixable = []

# Allow unused variables when underscore-prefixed
dummy-variable-rgx = "^(_+|(_+[a-zA-Z0-9_]*[a-zA-Z0-9]+?))$"

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["E402"]
"**/{tests,docs,tools}/*" = ["E402"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

### Rule selection patterns

```toml
[tool.ruff.lint]
# Start from defaults and add rule sets
select = ["E4", "E7", "E9", "F"]  # defaults (Pyflakes + pycodestyle errors)
extend-select = ["B", "I", "S"]   # add bugbear, isort, bandit

# Ignore specific rules
ignore = ["E501"]                   # ignore line-too-long (handled by formatter)

# Per-file exceptions
[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]               # allow assert in tests (bandit S101)
```

### Common rule set codes

| Code prefix | Source | Purpose |
|------------|--------|---------|
| `F` | Pyflakes | Undefined names, unused imports |
| `E`/`W` | pycodestyle | Style errors/warnings |
| `B` | flake8-bugbear | Common bugs and design problems |
| `I` | isort | Import sorting |
| `S` | bandit (flake8-bandit) | Security checks |
| `D` | pydocstyle | Docstring conventions |
| `UP` | pyupgrade | Python version upgrade suggestions |
| `RUF` | Ruff-specific | Ruff's own rules |

### Bandit security rule exceptions in this project

```toml
[tool.ruff.lint.per-file-ignores]
# These are intentional patterns in prothon:
"src/**" = [
    "S404",  # subprocess import (required for git/assistant invocation)
    "S603",  # subprocess call without shell=True (intended)
    "S607",  # partial executable path (shutil.which resolves full path)
]
"template/**" = ["S701"]  # Jinja2 autoescape (template rendering)
```

### isort configuration via ruff

```toml
[tool.ruff.lint.isort]
known-first-party = ["prothon"]
force-single-line = false
```

This enforces the import order: stdlib > third-party > local.

## Gotchas & Pitfalls

- **Ruff replaces multiple tools.** It covers Flake8, isort, pyupgrade, bandit, pydocstyle, and more. Do not install those tools separately when using ruff.
- **Ruff format is Black-compatible.** It uses the same formatting decisions (line length 88, double quotes, magic trailing commas). Projects migrating from Black need no changes.
- **`ruff check` and `ruff format` are separate commands.** Linting and formatting are independent operations. Run both in CI and pre-commit.
- **`--fix` applies safe fixes only.** Unsafe fixes (those that may change semantics) require `--unsafe-fixes`. In CI, run without `--fix` to only report issues.
- **Per-file ignores use glob patterns.** `"tests/*"` matches files in the `tests/` directory. `"**/tests/*"` matches recursively. The patterns are relative to the project root.
- **Rule conflicts with formatter.** Ruff automatically disables lint rules that conflict with its formatter (e.g., `E501` line-too-long when using `ruff format`). You can override this with `extend-select`.
- **`target-version` affects rule behavior.** Setting `target-version = "py311"` enables pyupgrade rules that suggest 3.11+ syntax. Keep this in sync with the project's minimum Python version.
- **Pre-commit integration.** Use `ruff-pre-commit` hooks for fastest execution. They run as native binaries, not Python scripts.

## Idiomatic Usage

**Do:** Run `ruff check --fix` and `ruff format` before committing. The pre-commit hooks handle this automatically.

**Don't:** Add `# noqa` comments without specifying the rule code. Always use `# noqa: E501` format to document which rule is being suppressed.

**Do:** Configure rules in `pyproject.toml` rather than via command-line flags. This ensures consistent behavior across developers and CI.

**Don't:** Override formatter settings unless the project has a specific reason. The Black-compatible defaults are well-tested.

**Do:** Use `per-file-ignores` for directory-specific exceptions rather than global `ignore` rules.

**Do:** Keep `target-version` in sync with the project's minimum Python version in `pyproject.toml`.
