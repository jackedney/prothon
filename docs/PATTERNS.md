# Implementation Patterns

## Code Organization

### Module Layout

Flat structure — one module per subsystem, as defined in DESIGN.md. Each module owns its public API at the top level. No re-exports through `__init__.py`.

```python
# __init__.py stays minimal
"""Prothon: docs-first Python project generator."""
__version__ = "0.1.0"
```

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | lowercase, singular nouns | `promise.py`, `scaffold.py`, `assistant.py` |
| Functions | `verb_noun` | `check_task()`, `find_project_root()`, `sync_skills()` |
| Private helpers | `_verb_noun` | `_git_diff_names()`, `_within_tolerance()` |
| Classes | PascalCase, no suffix noise | `CheckResult`, `Promise`, `Task` |
| Constants | `UPPER_SNAKE` at module level | `PROMISE_PATH`, `DEFAULT_TOLERANCE` |
| Type aliases | PascalCase | `DiffStat = dict[str, tuple[int, int]]` |

### Import Order

```python
from __future__ import annotations          # 1. future annotations (every file)

import subprocess                            # 2. stdlib (grouped, alphabetical)
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomlkit                               # 3. third-party (alphabetical)
import typer

from prothon.project import find_project_root  # 4. local (explicit names, no star imports)
from prothon.exceptions import PromiseError
```

### Module API Surface

Each module exposes a small public API. Internal helpers stay private. The `_` prefix convention is sufficient at this scale — no `__all__` needed.

```python
# promise.py — public API
def load_promise(path: Path = PROMISE_PATH) -> Promise: ...
def check_task(task_index: int, ...) -> TaskCheckReport: ...
def complete_task(task_index: int, ...) -> None: ...
def status(path: Path = PROMISE_PATH) -> str: ...
def plan(path: Path = PROMISE_PATH) -> str: ...
def cleanup(path: Path = PROMISE_PATH) -> None: ...

# Everything else is _private
def _git_diff_names(base_commit: str) -> set[str]: ...
def _within_tolerance(expected: int, actual: int) -> bool: ...
```

## Design Patterns

### Functions First, Classes When Needed

Most modules are plain functions with typed signatures. Reserve classes for two cases: **data carriers** (dataclasses) and **behavioral contracts** (protocols).

```python
# Plain function — the default
def check_task(task_index: int, *, path: Path = PROMISE_PATH) -> TaskCheckReport:
    ...

# Dataclass — for structured data
@dataclass
class TaskCheckReport:
    task_index: int
    title: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)
```

### Protocols for Dependency Injection

Use `typing.Protocol` for dependency injection boundaries where a module needs a swappable capability (primarily for testing). Protocols provide structural typing without inheritance.

```python
from typing import Protocol

class GitDiffProvider(Protocol):
    def diff_names(self, base_commit: str) -> set[str]: ...
    def diff_numstat(self, base_commit: str) -> dict[str, tuple[int, int]]: ...
```

Protocol implementations are standalone classes — they satisfy the contract structurally without inheriting from the protocol.

```python
class SubprocessGitDiff:
    def diff_names(self, base_commit: str) -> set[str]:
        result = subprocess.run(
            ["git", "diff", base_commit, "--name-only"],
            capture_output=True, text=True,
        )
        return {l for l in result.stdout.splitlines() if l}

    def diff_numstat(self, base_commit: str) -> dict[str, tuple[int, int]]:
        ...
```

### Protocol for Assistant Backends

The assistant backend contract is a protocol. Each backend is a plain class that structurally satisfies it — no inheritance required.

```python
class AssistantBackend(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def cli_command(self) -> str: ...

    def build_command(self, skill_name: str) -> list[str]: ...

    def sync_skills(self) -> None: ...


class ClaudeCodeBackend:
    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def cli_command(self) -> str:
        return "claude"

    def build_command(self, skill_name: str) -> list[str]:
        return [self.cli_command, "--skill", skill_name]

    def sync_skills(self) -> None:
        ...
```

### Registry for Backend Lookup

A simple dict maps names to factory callables. Used where a user or config string selects a concrete implementation at runtime.

```python
_BACKENDS: dict[str, type[AssistantBackend]] = {
    "claude-code": ClaudeCodeBackend,
}

def get_backend(name: str = "claude-code") -> AssistantBackend:
    cls = _BACKENDS.get(name)
    if cls is None:
        raise UnknownBackendError(name)
    return cls()
```

### Shared Lifecycle as Standalone Function

The shared launch lifecycle is a plain function that accepts anything satisfying `AssistantBackend`. This follows the "functions first" default — shared behavior doesn't require a base class.

```python
def launch(backend: AssistantBackend, skill_name: str, cwd: Path) -> int:
    """Shared assistant launch lifecycle."""
    if not shutil.which(backend.cli_command):
        raise AssistantNotFoundError(backend.cli_command)
    backend.sync_skills()
    return subprocess.run(backend.build_command(skill_name), cwd=cwd).returncode
```

### Default Arguments for Production, Parameters for Testing

Functions use production defaults but accept overrides so tests never touch real state.

```python
def load_promise(path: Path = PROMISE_PATH) -> Promise:
    ...

# In tests — no global state, no monkeypatching
def test_load_missing(tmp_path):
    report = load_promise(path=tmp_path / "nonexistent.toml")
```

### Pattern Summary

| Pattern | Where | Why |
|---------|-------|-----|
| Plain functions | Default for all modules | Simplest unit, easiest to test |
| Dataclasses | Data carriers (`Promise`, `CheckResult`, `Task`) | Typed, immutable-friendly, no boilerplate |
| Protocols | All dependency injection boundaries (`GitDiffProvider`, `AssistantBackend`) | Structural typing, no inheritance, swappable for testing |
| Standalone function | Shared lifecycle (`launch()`) | Keeps protocols pure interface, follows functions-first default |
| Registry dict | Backend lookup by name | Explicit, debuggable, no magic |
| Default args | Production vs test paths | Avoids monkeypatching |

## Error Handling

### Custom Exception Hierarchy

Flat hierarchy under a single base in `exceptions.py`. No deep trees.

```python
class ProthonError(Exception):
    """Base for all prothon errors. CLI catches this for clean exit."""

class ProjectNotFoundError(ProthonError):
    """No prothon project root found walking up from cwd."""

class PromiseError(ProthonError):
    """Promise file missing, malformed, or task index out of range."""

class AssistantNotFoundError(ProthonError):
    """Assistant CLI binary not found on PATH."""

class UnknownBackendError(ProthonError):
    """Backend name not in registry."""

class ComplianceError(ProthonError):
    """Compliance check found failures."""

class GitError(ProthonError):
    """Git subprocess command failed."""
```

### Raise at Source, Catch at Boundary

Domain modules raise specific exceptions. `cli.py` is the only place that catches `ProthonError` and converts it to a user-facing message with a non-zero exit code. Domain modules never call `sys.exit()` or print errors.

```python
# promise.py — raises, never prints
def load_promise(path: Path = PROMISE_PATH) -> Promise:
    if not path.exists():
        raise PromiseError(f"no promise file at {path}")
    ...

# cli.py — catches at the boundary
@app.command()
def status() -> None:
    try:
        report = promise.status()
        typer.echo(report)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
```

### No Bare Exceptions, No Silent Swallowing

Catch the specific failure, re-raise as a domain exception with context.

```python
# Good
try:
    data = tomllib.loads(text)
except tomllib.TOMLDecodeError as exc:
    raise PromiseError(f"malformed promise file: {exc}") from exc

# Bad — hides bugs
try:
    data = tomllib.loads(text)
except Exception:
    return None
```

### Subprocess Error Wrapping

The `git.py` wrapper converts subprocess failures immediately. Callers never see raw `subprocess.CalledProcessError`.

```python
def diff_names(base_commit: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", base_commit, "--name-only"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise GitError(f"git diff failed: {result.stderr.strip()}")
    return {l for l in result.stdout.splitlines() if l}
```

### Error Message Convention

Lowercase, specific, include the value that caused the problem.

```python
raise PromiseError(f"task index {task_index} out of range (0-{len(tasks) - 1})")
raise UnknownBackendError(f"no backend registered for '{name}'")
```

## Testing Patterns

### Test Layout

Mirror the source tree under `tests/`, one test file per module.

```
tests/
    conftest.py          # shared fixtures, fakes, factories
    test_promise.py
    test_scaffold.py
    test_git.py
    test_assistant.py
    test_compliance.py
    test_execute.py
    test_cli.py          # integration tests via Typer CliRunner
```

### Naming

- **Files:** `test_{module}.py`
- **Functions:** `test_{function}_{scenario}` — descriptive enough to diagnose failures from the name alone
- **No test classes** unless shared setup can't be handled by fixtures

```python
def test_check_task_passes_when_all_files_created(): ...
def test_check_task_fails_when_file_missing(): ...
def test_load_promise_raises_on_malformed_toml(): ...
def test_within_tolerance_boundary_values(): ...
```

### Protocol Fakes Over Mocks

Write simple fake implementations that satisfy protocols. Fakes are real code — they break when the protocol changes. Mocks don't.

```python
# conftest.py
class FakeGitDiff:
    def __init__(
        self,
        names: set[str] | None = None,
        stats: dict[str, tuple[int, int]] | None = None,
    ):
        self._names = names or set()
        self._stats = stats or {}

    def diff_names(self, base_commit: str) -> set[str]:
        return self._names

    def diff_numstat(self, base_commit: str) -> dict[str, tuple[int, int]]:
        return self._stats

# test_promise.py
def test_check_task_passes_when_all_files_created(tmp_path):
    write_promise(tmp_path / "promise.toml", tasks=[...])
    diff = FakeGitDiff(names={"src/foo.py"}, stats={"src/foo.py": (50, 0)})
    report = check_task(0, diff=diff, path=tmp_path / "promise.toml")
    assert report.passed
```

Reserve `unittest.mock` for cases where you genuinely can't control the dependency (e.g., patching `shutil.which`). Prefer restructuring to make fakes possible.

### Fixture Conventions

- `tmp_path` (built-in) for any test that touches the filesystem
- Shared fakes and factories in `conftest.py`
- **Factories over static fixtures** — functions with sensible defaults and keyword overrides:

```python
def make_task(
    title: str = "test task",
    files_to_create: list[str] | None = None,
    expected_lines_added: int = 50,
    **overrides,
) -> dict:
    base = {
        "title": title,
        "files_to_create": files_to_create or [],
        "files_to_modify": [],
        "files_to_remove": [],
        "expected_lines_added": expected_lines_added,
        "expected_lines_removed": 0,
        "completed": False,
        "attempts": 0,
    }
    return {**base, **overrides}
```

### Hypothesis for Boundary Logic

Use Hypothesis for functions with numeric or string boundaries — tolerance checks, path parsing, TOML roundtrips.

```python
from hypothesis import given, strategies as st

@given(expected=st.integers(0, 10000), actual=st.integers(0, 10000))
def test_within_tolerance_is_symmetric(expected, actual):
    from prothon.promise import _within_tolerance
    assert _within_tolerance(expected, actual) == _within_tolerance(actual, expected)
```

Don't use Hypothesis for everything — plain `parametrize` is clearer for known edge cases.

### CLI Integration Tests

Test CLI commands via Typer's `CliRunner`, not subprocess. Fast and in-process.

```python
from typer.testing import CliRunner
from prothon.cli import app

runner = CliRunner()

def test_status_shows_progress(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_promise(tmp_path / "docs" / "change_promise.toml", ...)
    result = runner.invoke(app, ["promise", "status"])
    assert result.exit_code == 0
    assert "0/3 tasks completed" in result.output
```

### What Not to Test

- Third-party library behavior (Typer routing, tomlkit parsing)
- Trivial dataclass construction
- Private helpers — unless they contain non-obvious logic (like `_within_tolerance`)
