---
name: style-python
description: Code style conventions for Python in this project
user-invocable: false
---

# Python Code Style

> Style guide: PEP 8 (https://peps.python.org/pep-0008/), enforced by ruff
> Tooling: ruff (linting + formatting), ty (type checking)

## Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Modules | `snake_case` | `scaffold.py`, `promise.py` |
| Classes | `PascalCase` | `AssistantBackend`, `TaskCheckReport` |
| Functions/methods | `snake_case` | `find_project_root()`, `sync_skills()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TOLERANCE` |
| Local variables | `snake_case` | `task_index`, `base_commit` |
| Private members | `_leading_underscore` | `_registry`, `_parse_diff()` |
| Type variables | `PascalCase` or single uppercase | `T`, `PathLike` |
| Protocol classes | `PascalCase` with descriptive name | `GitDiffProvider` |
| Dataclasses | `PascalCase` | `Task`, `Metadata`, `Promise` |
| Enum members | `UPPER_SNAKE_CASE` | `CheckStatus.PASS`, `CheckStatus.FAIL` |

## Import & Module Structure

**Import order** (enforced by ruff's isort rules):

1. Standard library (`pathlib`, `subprocess`, `dataclasses`)
2. Third-party (`typer`, `copier`, `tomlkit`)
3. Local (`from prothon.project import find_project_root`)

Blank line between each group. Within groups, sort alphabetically.

**Import style:**
```python
# Preferred: import specific names
from pathlib import Path
from dataclasses import dataclass, field

# Acceptable: module import for namespacing
import tomlkit
import subprocess

# Avoid: wildcard imports
from os.path import *  # never
```

**Module layout:**
1. Module docstring (one sentence describing purpose)
2. `__all__` (if public API is a subset of module contents)
3. Imports (grouped as above)
4. Constants
5. Type aliases / protocols
6. Classes
7. Functions
8. No `if __name__ == "__main__"` in library modules

## Type Annotations

This project uses `ty` for type checking. Annotate all public function signatures.

```python
# Public functions: fully annotated
def find_project_root(start: Path | None = None) -> Path:
    ...

# Dataclass fields: annotated (required by dataclass)
@dataclass
class Task:
    title: str
    completed: bool = False
    files_to_create: list[str] = field(default_factory=list)

# Protocol for dependency injection
class GitDiffProvider(Protocol):
    def diff_numstat(self, base: str, head: str) -> list[DiffStat]: ...

# Private/helper functions: annotate if non-obvious
def _parse_numstat_line(line: str) -> tuple[int, int, str]:
    ...
```

**Modern syntax preferences (Python 3.11+ -- project minimum):**
- `X | Y` over `Union[X, Y]`
- `list[str]` over `List[str]`
- `dict[str, Any]` over `Dict[str, Any]`
- `tuple[int, ...]` over `Tuple[int, ...]`
- No need for `from __future__ import annotations` (3.11+ supports PEP 604 natively)

## Documentation

**Docstring style:** Google style (compatible with ruff D rules).

```python
def check_task(
    task_index: int,
    *,
    diff: GitDiffProvider | None = None,
    path: Path = PROMISE_PATH,
) -> TaskCheckReport:
    """Check a single task's promises against git reality.

    Args:
        task_index: Zero-based index of the task to check.
        diff: Git diff data source; defaults to SubprocessGitDiff().
        path: Path to the promise TOML file.

    Returns:
        Report with per-check PASSED/FAILED/SKIPPED details.

    Raises:
        PromiseError: If task_index is out of range.
    """
```

- All public classes and functions get docstrings.
- Private helpers get docstrings only if behavior is non-obvious.
- Module-level docstrings describe the module's purpose in one sentence.

## Formatting Rules

**Auto-enforced by ruff format:**
- Line length: 88 characters (Black default)
- Indentation: 4 spaces (no tabs)
- String quotes: double quotes (`"string"`)
- Trailing commas: preserved (magic trailing comma respected)
- Parenthesized line continuations over backslash

**Manual conventions:**
- Group related classes in one module (e.g., `Task`, `Metadata`, `Promise` in `promise.py`)
- Blank lines: 2 between top-level definitions, 1 between methods
- f-strings preferred over `.format()` or `%`
- `Path` objects over string paths throughout
- Context managers (`with`) for file I/O and subprocesses
- Keyword-only arguments (after `*`) for functions with >2 parameters
- `@dataclass` for data containers; avoid raw `__init__` when fields are the primary concern
