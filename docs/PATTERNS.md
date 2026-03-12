# Implementation Patterns

## Code Organization

### Module Layout

Flat structure — one module per subsystem, as defined in DESIGN.md. Each module owns its public API at the top level. No re-exports through `__init__.py` beyond the version string.

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | lowercase, singular nouns | `promise.py`, `scaffold.py`, `assistant.py` |
| Functions | `verb_noun` | `check_task()`, `find_project_root()`, `sync_skills()` |
| Private helpers | `_verb_noun` | `_git_diff_names()`, `_within_tolerance()` |
| Classes | PascalCase, no suffix noise | `CheckResult`, `Promise`, `Task` |
| Constants | `UPPER_SNAKE` at module level | `PROMISE_PATH`, `DEFAULT_TOLERANCE` |
| Inline content | `_UPPER_SNAKE` private constant | `_SPEC_SCAFFOLD`, `_AGENTS_CONTENT` |
| Type aliases | PascalCase | `DiffStat = dict[str, tuple[int, int]]` |

### Import Order

Four groups, separated by blank lines, each group alphabetical: (1) `from __future__ import annotations` in every file, (2) stdlib, (3) third-party, (4) local with explicit names — no star imports.

### Module API Surface

Each module exposes a small public API. Internal helpers use the `_` prefix. No `__all__` — the underscore convention is sufficient at this scale. Public signatures per module:

**promise.py:**
```python
def load_promise(path: Path = PROMISE_PATH) -> Promise: ...
def save_promise(promise: Promise, path: Path = PROMISE_PATH) -> None: ...
def check_task(task_index: int, *, diff: GitDiffProvider | None = None, path: Path = PROMISE_PATH) -> TaskCheckReport: ...
def complete_task(task_index: int, *, diff: GitDiffProvider | None = None, path: Path = PROMISE_PATH) -> None: ...
def record_attempt(task_index: int, *, path: Path = PROMISE_PATH) -> None: ...
def status(path: Path = PROMISE_PATH) -> str: ...
def plan(path: Path = PROMISE_PATH) -> str: ...
def cleanup(path: Path = PROMISE_PATH) -> None: ...
```

**scaffold.py:**
```python
def generate(dest: Path, data: dict | None = None) -> None: ...
def init_existing(cwd: Path | None = None) -> list[Path]: ...
```

**project.py:**
```python
def find_project_root(start: Path | None = None) -> Path: ...
```

**git.py:**
```python
def run_git(*args: str, cwd: Path | None = None) -> str: ...
def rev_parse_head(cwd: Path | None = None) -> str: ...
def is_dirty(path: Path, cwd: Path | None = None) -> bool: ...
def commit_file(path: Path, message: str, cwd: Path | None = None) -> None: ...
```

**skills.py:**
```python
def bundled_skills_dir() -> Path: ...
def sync_skills(target: Path | None = None) -> None: ...
```

**assistant.py:**
```python
def register_backend(name: str, cls: type) -> None: ...
def get_backend(name: str = "claude-code") -> AssistantBackend: ...
def launch(backend: AssistantBackend, skill_name: str, cwd: Path, model: str | None = None) -> int: ...
```

**versioning.py:**
```python
def parse_version(v: str) -> tuple[int, int, int]: ...
def bump_major(v: str) -> str: ...
def bump_minor(v: str) -> str: ...
def bump_patch(v: str) -> str: ...
def update_pyproject_version(path: Path, new_version: str) -> None: ...
def update_init_version(path: Path, new_version: str) -> None: ...
def create_tag(version: str, cwd: Path | None = None) -> None: ...
def detect_bump_type(before_sha: str, after_sha: str, cwd: Path | None = None) -> str | None: ...
```

## Design Patterns

### Functions First, Classes When Needed

Most modules are plain functions with typed signatures. Reserve classes for two cases: **data carriers** (dataclasses) and **behavioral contracts** (protocols). If a piece of logic doesn't need state between calls, it's a function.

### Dataclasses for Structured Data

Use `@dataclass` with `field(default_factory=...)` for mutable defaults. Dataclasses carry data and may expose computed properties, but should not contain complex business logic. The promise system uses this for `Task`, `Metadata`, `Promise`, `CheckResult`, `FileCheckDetail`, and `TaskCheckReport`.

### Protocols for Dependency Injection

Use `typing.Protocol` where a module needs a swappable capability — primarily for testing. Protocols provide structural typing without inheritance. Implementations satisfy the contract structurally without inheriting from the protocol.

### Registry for Backend Lookup

A module-level dict maps string names to backend classes. A `register_backend()` function provides a public extension hook for programmatic use and testing. `get_backend()` instantiates by name, listing all registered backends in the error message when the name is unknown.

### Shared Lifecycle as Standalone Function

The `launch()` function accepts anything satisfying `AssistantBackend` and runs the shared lifecycle: binary existence check, skill syncing, environment merging, subprocess execution, and return code reporting.

### File Locking and Atomic Persistence

When parallel subagents mark tasks complete simultaneously, the promise TOML file is a shared resource. `complete_task()` wraps its load → modify → save cycle in an exclusive file lock to prevent lost updates. `save_promise()` writes atomically via temporary files and `os.replace`.

The lock implementation is cross-platform: `fcntl.flock` on Unix, `msvcrt.locking` on Windows. The lock uses a sibling `.toml.lock` file.

### Guard-Clause Preconditions

Domain functions that require specific environmental conditions validate them upfront and raise domain exceptions. Guards come first, happy path follows. No nested `if/else` trees.

### Hybrid Verification Pattern

Used by the compliance checker. It combines deterministic static analysis (regex or AST) for structural requirements and documentation form rules with semantic LLM-based analysis for high-level functional requirements.

### Evidence-Based Verification

All verification and compliance reports must map findings to source code evidence. Every PASS/FAIL status must include a `file:line` citation and a brief rationale explaining how the implementation satisfies or fails the documented intent.

### Advisory-First Refactoring

The refactoring workflow is split into two distinct phases. The **Discovery Phase** is purely advisory and read-only; it scans for drift and presents findings to the user. The **Execution Phase** only begins after the user selects specific improvements, triggering the generation of a change promise and subsequent implementation tasks.

### Refactor Wave Pattern

Changes flow top-down through the documentation hierarchy: **DESIGN -> PATTERNS -> CODE**. Architectural shifts or convention changes must be documented and approved before any source code is modified. Implementation tasks must reference the specific documentation heading they are aligning with.

### Hierarchical Conflict Resolution

When the `doc-harmonizer` detects contradictions, it presents them as "Before/After" diffs based on the authority hierarchy (SPEC > DESIGN > PATTERNS). Higher-level documents are never amended by the harmonizer; only lower-authority documents are updated after explicit user approval.

### Self-Correcting Subagent Loop

Orchestrated tasks follow an iterative **Plan -> Act -> Validate** cycle. Each task executes in a fresh subagent context, followed by a quality gate (pre-commit hooks) and a verification check (promise check). If either fails, the task is retried up to `max_attempts`.

### Default Arguments for Production, Parameters for Testing

Functions use production defaults but accept overrides so tests never touch real state and never need monkeypatching.

### XDG_CONFIG_HOME Resolution

Backends and configuration readers respect `$XDG_CONFIG_HOME` with a `~/.config` fallback. Empty or relative values fall back to `~/.config`.

### Fallthrough Precedence Chain

Configuration resolution (agent, model, provider) implements a multi-level precedence chain: CLI flag > env var > pyproject.toml > global config > default. The first non-empty value wins.

## Skill Authoring Patterns

### Frontmatter Conventions

All bundled skills live in `src/prothon/skills/` as directories containing a `SKILL.md`. Frontmatter fields include `name`, `description`, and optional assistant-specific fields like `model` or `context`.

### Multi-File Skill Layout (Progressive Disclosure)

Generated reference skills follow a hierarchical structure to maintain context efficiency. `SKILL.md` contains the core instructions and concise usage patterns (< 500 words). Detailed API specifications, heavy documentation, or large examples (> 100 lines) are moved to a `references/` subdirectory.

### Canonical Subagent Portability

Skills must use **canonical agent type names** (`general-purpose`, `explore`, `plan`) when requesting subagent spawns. Each assistant backend's `subagent_type_map` translates these canonical names into tool-specific invocations, ensuring skills are portable across different AI assistants.

### Conversational Cadence

User-facing doc-writer skills enforce a one-message-then-wait cadence. This prevents context dumping and ensures incremental user control over design and requirements decisions.

### Documentation Safety in Skills

Non-doc agents explicitly declare `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` as read-only. Skills authorized to write to docs must perform a local git commit immediately after writing to prevent state loss.

## Error Handling

### Custom Exception Hierarchy

A flat hierarchy under `ProthonError` in `exceptions.py` provides domain-specific failure modes. `cli.py` serves as the single boundary for catching these and presenting formatted messages.

### Terminal Failure Pattern

When a subagent reaches `max_attempts` for a task without passing verification and quality gates, it reports a terminal failure. The orchestrator records the failure and the full attempt log, then asks the user for a decision (skip, retry, or abort).

### Doc Consistency Failures

Contradictions found by the `doc-harmonizer` are treated as data rather than exceptions. They are presented as a structured report of `Conflict` objects, enabling interactive resolution and approval before any documents are amended.

### Compliance Failure Pattern

Compliance checking produces a report of `CheckResult` objects with `CheckStatus.FAILED` for unmet requirements. These are not treated as flow-control exceptions unless specifically running in a CI environment where a non-zero exit code is required for failure.

## Testing Patterns

### Test Layout

The `tests/` directory mirrors the `src/prothon/` layout. Shared fixtures and factories are centralized in `conftest.py`.

### Protocol Fakes Over Mocks

Test dependencies are managed using simple fake implementations that satisfy protocols. This ensures tests break when interfaces change, providing better safety than standard mocks.

### Subagent Mocking Pattern

Use a `FakeAssistantBackend` that simulates subagent responses, return codes, and file modifications. This enables testing complex orchestration logic (like the Refactor Wave or Task Lifecycle) without invoking real AI models.

### Conflict Injection Pattern

Verify the `doc-harmonizer` by injecting known contradictions between SPEC, DESIGN, and PATTERNS. Tests confirm that the harmonizer detects the conflict, identifies the correct higher-authority document, and proposes the appropriate resolution text.

### Concurrency Stress Testing

Verify the `.toml.lock` exclusive locking mechanism by using multiprocessing to simulate concurrent subagents attempting to mark tasks complete simultaneously. Tests ensure that all updates are serialized and no data is lost.
