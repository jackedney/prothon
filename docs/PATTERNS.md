# Implementation Patterns

> **Progressive disclosure:** Per-module API signatures live in `docs/references/modules.md` and are loaded as needed via `context_files` entries in `change_promise.toml`. This file focuses on patterns, conventions, and rationale — not inline module signatures.

## Code Organization

### Module Layout
Prefer a flat structure — one module per subsystem, except where a logical subpackage is needed (e.g., `src/prothon/checks/` groups related static compliance checks). Domain modules remain plain Python, independent of any CLI framework.

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | lowercase, singular nouns | `promise.py`, `ui.py`, `config.py` |
| Functions | `verb_noun` | `resolve_agent()`, `render_compliance_report()` |
| Private helpers | `_verb_noun` | `_git_diff_names()`, `_within_tolerance()` |
| Classes | PascalCase, no suffix noise | `CheckResult`, `Promise`, `Task` |
| Backend Classes | `<Name>Backend` | `ClaudeBackend`, `GeminiBackend` |
| Protocols | PascalCase nouns | `AssistantBackend`, `GitDiffProvider` |
| Constants | `UPPER_SNAKE` at module level | `PROMISE_PATH`, `DEFAULT_TOLERANCE` |
| Type aliases | PascalCase | `DiffStat = dict[str, tuple[int, int]]` |

### Import Order
Four groups, separated by blank lines, each group alphabetical: (1) `from __future__ import annotations` in every file, (2) stdlib, (3) third-party, (4) local with explicit names — no star imports.

### Module API Surface
Each module exposes a minimal public API. Internal helpers use the `_` prefix. Following the Progressive Disclosure Documentation Pattern, per-module API signatures are maintained in Level 3 documentation (`docs/references/modules.md`) to keep this document concise and fast for AI assistants to parse.

## Design Patterns

### Progressive Disclosure Documentation Pattern
To maintain context efficiency for AI assistants, all projects follow a three-level documentation hierarchy. **Level 1** (YAML/Metadata) provides high-level discovery and triggering. **Level 2** (Main Markdown files) contains core instructions, rationale, and behavioral logic. **Level 3** (`docs/references/` subdirectory) holds detailed API specifications and complex examples. This ensures assistants only load heavy context when specifically relevant to their current task.

### Tiered Compliance Evidence Pattern
Compliance verification uses a hybrid strategy: static analysis (AST/Regex) handles structural rules like method signatures, while semantic analysis (LLM subagents) verifies high-level behavioral requirements. Every check produces a report with a tri-state status (`PASS`, `FAIL`, `SKIP`), a `file:line` evidence citation, and a brief rationale.

### Pluggable Assistant Backend Pattern
To support multiple AI assistants (Claude Code, opencode, Gemini CLI) with identical behavior, the system uses a pluggable backend architecture defined by the `AssistantBackend` protocol. Each backend handles its own CLI command construction and skill synchronization.

```python
class AssistantBackend(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def cli_command(self) -> str: ...
    @property
    def install_hint(self) -> str: ...
    def build_command(self, skill_name: str, cwd: Path, model: str | None = None) -> list[str]: ...
    def sync_skills(self) -> None: ...
    def env_overrides(self) -> dict[str, str]: ...
    def subagent_type_map(self) -> dict[str, str]: ...
```

### Heuristic-based Logic Detection Pattern
Following the "Test Value Over Test Count" philosophy, the system uses AST heuristics to identify "testable logic" (e.g., non-trivial branching or calculations). This allows automated tools to detect missing tests only for modules that truly require them, avoiding redundant coverage of trivial pass-through code.

```python
def _is_trivial_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool: ...
def _is_testable_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool: ...
def _is_testable_class(node: ast.ClassDef) -> bool: ...
```

### Session Command Wrapper Pattern
To ensure consistent error handling across all six CLI session commands (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`), the system uses a centralized wrapper to catch domain-specific errors and present them via `typer.echo(str(exc), err=True)`.

```python
def _run_session_command(cmd: Callable[..., int | None], agent: str | None, model: str | None, provider: str | None) -> None: ...
```

## Error Handling

### Centralized CLI Error Boundary
The `cli.py` module acts as the single catch-all boundary for `ProthonError` and its subclasses. Library modules raise domain-specific exceptions; the CLI catches them, presents a formatted message through the terminal UI, and terminates with a non-zero exit code.

### Path Existence Guard Pattern
Before any filesystem operation that assumes a path exists (or does not exist), verify the path using `Path` methods and raise an actionable `ProthonError` subclass if the check fails. Positive guards verify existence; negative guards prevent illegal state transitions.

```python
def find_project_root(start: Path | None = None) -> Path: ...
def init_project(cwd: Path | None = None) -> None: ...
```

### File I/O Error Handling Pattern
File operations that scan large directory trees or load non-essential configuration use a "silently degrade" pattern. By catching `OSError` and returning a safe default (like an empty list or string), the system maintains stability during batch operations.

```python
# fs.py utilities
def file_hash(path: Path) -> str | None: ...
def safe_parse_py(path: Path) -> tuple[ast.Module, str] | None: ...
def atomic_write(target: Path, data: bytes) -> None: ...
def create_agent_symlinks(root: Path, agents_path: Path) -> list[Path]: ...
def xdg_config_home() -> Path: ...

# checks/utils.py utilities
def analyze_python_file(path: Path) -> dict[str, Any]: ...
```

### Terminal Failure Pattern
When a subagent reaches its `max_attempts` for a task without passing verification, it reports a terminal failure. The orchestrator records this state and prompts the user for a decision (skip, retry, or abort), preventing infinite loops.

```python
def record_attempt(task_index: int, path: Path = PROMISE_PATH) -> None: ...
```

## Testing Patterns

### Test Value Over Test Count
Prioritize fewer, higher-value tests over comprehensive coverage. Avoid testing trivial code (simple getters/setters), language features, framework behavior, or redundant coverage across levels. Focus on business logic, edge cases, integration points, and system invariants.

### Lightweight, Fast Tests
The full test suite should complete in seconds. Keep tests lightweight by using fakes/stubs instead of real services, preferring in-memory structures over temp files, and isolating units to avoid loading heavy dependency graphs.

### Protocol Fakes Over Mocks
Manage test dependencies using simple fake implementations that satisfy protocols. This ensures tests break when interfaces change and avoids the fragility of standard mocking libraries.

```python
class FakeGitDiff:
    def get_diff(self, before: str, after: str) -> DiffStat: ...
```

### Subagent Mocking Pattern
Orchestration and retry logic are tested using a `FakeAssistantBackend` that simulates subagent responses and file modifications. This enables exhaustive testing of the implementation workflow without hitting real AI APIs.

```python
class FakeAssistantBackend:
    def build_command(self, skill_name: str, cwd: Path, model: str | None = None) -> list[str]: ...
```
