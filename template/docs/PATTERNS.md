# Implementation Patterns

> **Progressive disclosure:** Per-module API signatures live in `docs/references/` and are loaded as needed via `context_files` entries in `change_promise.toml`. This file focuses on patterns, conventions, and rationale — not inline module signatures.

## Code Organization

### Module Layout
Prefer a flat structure — one module per subsystem, except where a logical subpackage is needed for grouping related functionality. Domain modules remain plain Python, independent of any external frameworks where possible.

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | lowercase, singular nouns | `service.py`, `models.py`, `config.py` |
| Functions | `verb_noun` | `calculate_total()`, `format_report()` |
| Private helpers | `_verb_noun` | `_validate_input()`, `_parse_config()` |
| Classes | PascalCase, no suffix noise | `UserRecord`, `Transaction`, `Config` |
| Protocols | PascalCase nouns | `DataProvider`, `NotificationService` |
| Constants | `UPPER_SNAKE` at module level | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Type aliases | PascalCase | `JSONDict = dict[str, Any]` |

### Import Order
Four groups, separated by blank lines, each group alphabetical: (1) `from __future__ import annotations` in every file, (2) stdlib, (3) third-party, (4) local with explicit names — no star imports.

### Module API Surface
Each module exposes a minimal public API. Internal helpers use the `_` prefix. Following the Progressive Disclosure Documentation Pattern, per-module API signatures are maintained in Level 3 documentation (`docs/references/`) to keep this document concise and fast for AI assistants to parse.

## Design Patterns

### Progressive Disclosure Documentation Pattern
To maintain context efficiency for AI assistants, this project follows a three-level documentation hierarchy. **Level 1** (YAML/Metadata) provides high-level discovery and triggering. **Level 2** (Main Markdown files) contains core instructions, rationale, and behavioral logic. **Level 3** (`docs/references/` subdirectory) holds detailed API specifications and complex examples. This ensures assistants only load heavy context when specifically relevant to their current task.

### Tiered Compliance Evidence Pattern
Compliance verification uses a hybrid strategy: static analysis (AST/Regex) handles structural rules like method signatures, while semantic analysis (LLM subagents) verifies high-level behavioral requirements. Every check produces a report with a tri-state status (`PASS`, `FAIL`, `SKIP`), a `file:line` evidence citation, and a brief rationale.

### Service Protocol Pattern
To decouple core logic from implementation details and improve testability, the system uses Protocols to define service contracts. This allows for easy swapping of implementations and the use of fakes in tests.

```python
class DataProvider(Protocol):
    def fetch_data(self, query: str) -> list[dict]: ...
    def save_data(self, data: list[dict]) -> None: ...
```

## Error Handling

### Centralized Error Boundary
Identify a single catch-all boundary (e.g., a CLI entry point or a top-level middleware) for domain-specific exceptions. Library modules raise exceptions; the boundary catches them, presents a formatted message, and terminates or responds appropriately.

### Path Existence Guard Pattern
Before any filesystem operation that assumes a path exists (or does not exist), verify the path using `Path` methods and raise an actionable domain-specific exception if the check fails. Positive guards verify existence; negative guards prevent illegal state transitions.

```python
def load_configuration(path: Path) -> Config: ...
def create_project_dir(path: Path) -> None: ...
```

### File I/O Error Handling Pattern
File operations that scan large directory trees or load non-essential configuration use a "silently degrade" pattern. By catching `OSError` and returning a safe default (like an empty list or string), the system maintains stability during batch operations.

```python
def scan_user_files(root: Path) -> list[Path]: ...
def read_optional_meta(path: Path) -> str: ...
```

## Testing Patterns

### Test Value Over Test Count
Prioritize fewer, higher-value tests over comprehensive coverage. Avoid testing trivial code (simple getters/setters), language features, framework behavior, or redundant coverage across levels. Focus on business logic, edge cases, integration points, and system invariants.

### Lightweight, Fast Tests
The full test suite should complete in seconds. Keep tests lightweight by using fakes/stubs instead of real services, preferring in-memory structures over temp files, and isolating units to avoid loading heavy dependency graphs.

### Protocol Fakes Over Mocks
Manage test dependencies using simple fake implementations that satisfy protocols. This ensures tests break when interfaces change and avoids the fragility of standard mocking libraries.

```python
class FakeDataProvider:
    def fetch_data(self, query: str) -> list[dict]: ...
```
