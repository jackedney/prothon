# Implementation Patterns

## Code Organization

### Module Layout

Flat structure — one module per subsystem, as defined in DESIGN.md. CLI logic is distributed: `cli.py` (Typer app/commands), `ui.py` (Rich-based terminal rendering), `config.py` (configuration resolution), and `scaffold_cli.py` (interactive scaffolding). Domain modules remain plain Python, independent of the CLI framework.

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | lowercase, singular nouns | `promise.py`, `ui.py`, `config.py` |
| Functions | `verb_noun` | `resolve_agent()`, `render_compliance_report()` |
| Private helpers | `_verb_noun` | `_git_diff_names()`, `_within_tolerance()` |
| Classes | PascalCase, no suffix noise | `CheckResult`, `Promise`, `Task` |
| Backend Classes | `<Name>Backend` | `ClaudeBackend`, `GeminiBackend` |
| Constants | `UPPER_SNAKE` at module level | `PROMISE_PATH`, `DEFAULT_TOLERANCE` |
| Type aliases | PascalCase | `DiffStat = dict[str, tuple[int, int]]` |

### Import Order

Four groups, separated by blank lines, each group alphabetical: (1) `from __future__ import annotations` in every file, (2) stdlib, (3) third-party, (4) local with explicit names — no star imports.

### Module API Surface

Each module exposes a minimal public API. Internal helpers use the `_` prefix.

**cli.py:**
```python
app = typer.Typer(...)        # Main CLI entry point
promise_app = typer.Typer(...)  # `prothon promise` subcommands
ci_app = typer.Typer(...)       # `prothon ci` subcommands
```

**commands.py:**
```python
def spec_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def design_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def patterns_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def execute_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def compliance_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> None: ...
def refactor_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
```

**ui.py:**
```python
def render_compliance_report(report: ComplianceReport) -> Table: ...
def render_plan(promise: Promise) -> Panel: ...
def render_status(promise: Promise) -> Table: ...
```

**config.py:**
```python
def file_hash(path: Path) -> str | None: ...
def find_init_path(root: Path, project_name: str, module_name: str) -> Path | None: ...
def read_toml(path: Path) -> dict: ...
def nested_get(doc: dict, *keys: str) -> str | None: ...
def resolve_agent(cli_value: str | None = None) -> str: ...
def resolve_model(cli_model: str | None, cli_provider: str | None) -> str | None: ...
```

**assistant.py:**
```python
def register_backend(name: str, cls: type) -> None: ...
def get_backend(name: str = "claude-code") -> AssistantBackend: ...
def launch(backend: AssistantBackend, skill_name: str, cwd: Path, model: str | None = None) -> int: ...
```

**compliance.py:**
```python
def run_static_checks(root: Path) -> ComplianceReport: ...
def run_semantic_checks(root: Path, agent: str, model: str | None = None) -> ComplianceReport: ...
```

**refactor.py:**
```python
def discover_drift(root: Path) -> list[DriftFinding]: ...
def generate_refactor_promise(findings: list[DriftFinding]) -> Promise: ...
```

## Design Patterns

### Tiered Compliance Evidence Pattern
Compliance verification uses a hybrid strategy to map requirements to source code. **Static Analysis** (Regex/AST) performs fast, deterministic checks for structural rules and doc formats. **Semantic Analysis** (LLM-based) handles high-level functional requirements. Both feed into **Evidence Mapping**, where every result is paired with a `file:line` citation and a brief rationale.

### Progressive Disclosure Skill Pattern
To maintain context efficiency for AI assistants, generated reference skills follow a three-level hierarchy. **Level 1** (YAML frontmatter) provides trigger phrases for discovery. **Level 2** (`SKILL.md` body) contains core instructions. **Level 3** (`references/` subdirectory) holds detailed API specs and heavy examples, loaded only when needed.

### Refactor Wave Pattern
Changes must flow top-down through the documentation hierarchy: **DESIGN -> PATTERNS -> CODE**. Architectural shifts or convention changes are documented and approved first. Implementation tasks then reference the specific documentation heading they are aligning with.

### File Locking and Atomic Persistence
When parallel subagents mark tasks complete simultaneously, the promise TOML file is a shared resource. `complete_task()` wraps its load → modify → save cycle in an exclusive file lock to prevent lost updates, using a sibling `.toml.lock` file.

## Error Handling

### Centralized CLI Error Boundary
The `cli.py` module acts as the single catch-all boundary for `ProthonError` and its subclasses. Library modules raise exceptions; the CLI catches them, presents a formatted message, and terminates with a non-zero exit code.

### Terminal Failure Pattern
When a subagent reaches `max_attempts` for a task without passing verification and quality gates, it reports a terminal failure. The orchestrator records the failure and asks the user for a decision (skip, retry, or abort) to prevent infinite loops.

### Data-Driven Doc Consistency Failures
Contradictions found by the `doc-harmonizer` are treated as data, not exceptions. They are presented as a structured report of `Conflict` objects, enabling interactive resolution and approval before any documents are amended.

### Model/Provider Resolution Errors
Configuration resolution for `opencode` enforces that both model and provider must be present if one is provided. Violations raise a `ConfigurationError` explaining the required format, ensuring early failure.

## Testing Patterns

### Protocol Fakes Over Mocks
Test dependencies are managed using simple fake implementations that satisfy protocols (e.g., `FakeGitDiff` for `GitDiffProvider`). This ensures tests break when interfaces change and avoids fragile standard mocks.

### Subagent Mocking Pattern
Orchestration logic is tested using a `FakeAssistantBackend` that simulates subagent responses, return codes, and file modifications. This enables exhaustive testing of retry loops and decision-making without hitting real APIs.

### Conflict Injection Pattern
The `doc-harmonizer` is verified by injecting known contradictions between SPEC, DESIGN, and PATTERNS. Tests confirm the harmonizer detects the conflict, identifies the higher-authority document, and proposes the correct resolution.

### Concurrency Stress Testing
The `.toml.lock` exclusive locking mechanism is verified using multiprocessing to simulate concurrent subagents. Tests ensure all updates are serialized and no data is lost.
