# Implementation Patterns

## Code Organization

### Module Layout

Prefer a flat structure — one module per subsystem, except where a logical subpackage is needed (e.g., `src/prothon/checks/` groups related static compliance checks). The concrete list of modules and their responsibilities is maintained in DESIGN.md. Domain modules remain plain Python, independent of the CLI framework.

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

Per-module API surface signatures live in `docs/references/modules.md`, organized by module in the same order they appear in DESIGN.md's Module Structure section. Subagents load these signatures as needed via `context_files` entries in `change_promise.toml`, keeping the core patterns document concise. Modules whose contracts are fully described in DESIGN.md (compliance.py, models.py, promise_verify.py, git.py) are noted with a cross-reference rather than duplicated. See the Tech-Researcher section in DESIGN.md for the full progressive disclosure architecture.

## Design Patterns

### Tiered Compliance Evidence Pattern

Compliance verification uses a hybrid strategy to map requirements to source code. **Static Analysis** (Regex/AST) performs fast, deterministic checks for structural rules and doc formats. **Semantic Analysis** (LLM-based) handles high-level functional requirements. Both feed into **Evidence Mapping**, where every result is paired with a `file:line` citation and a brief rationale.

### Progressive Disclosure Skill Pattern

To maintain context efficiency for AI assistants, generated reference skills follow a three-level hierarchy. **Level 1** (YAML frontmatter) provides trigger phrases for discovery. **Level 2** (`SKILL.md` body) contains core instructions. **Level 3** (`references/` subdirectory) holds detailed API specs and heavy examples, loaded only when needed.

### Parallel Refactor Execution

Changes must flow top-down through the documentation hierarchy: **DESIGN -> PATTERNS -> CODE**. Architectural shifts or convention changes are documented and approved first. Implementation tasks then reference the specific documentation heading they are aligning with.

When parallel subagents mark tasks complete simultaneously, the promise TOML file is a shared resource. `complete_task()` wraps its load → modify → save cycle in an exclusive file lock (via a sibling `.toml.lock` file) to prevent lost updates.

This concurrency mechanism supports the wave principle by allowing independent tasks within a wave to execute in parallel while maintaining data integrity. The lock covers the full read-modify-write cycle so no completion is overwritten by a racing subagent.

### Session Command Wrapper Pattern

**Problem:** The six session commands in `cli.py` (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) each repeat an identical error-handling block: resolve the project root, call the corresponding `commands.*_command()` function inside a `try/except ProthonError`, format the error, and exit.

**Convention:** `cli.py` uses `_run_session_command` to wrap every session command with the standard error boundary:

```python
def _run_session_command(
    cmd: Callable[..., int | None],
    agent: str | None,
    model: str | None,
    provider: str | None,
) -> None: ...
```

Each session command is a thin Typer-decorated function that delegates:

```python
@app.command()
def spec(agent: AgentOption = None, model: ModelOption = None,
         provider: ProviderOption = None) -> None: ...
```

**Rationale:** All six commands share a single error-handling path (DRY), every command follows the same `ProthonError → stderr → exit(1)` path (consistency), the wrapper handles both `int` and `None` return codes uniformly (correctness), and new session commands require only the Typer decorator plus delegation (extensibility).

### Path Existence Guard Pattern

Before any filesystem operation that assumes a path exists, check using `Path` methods (`.is_dir()`, `.is_file()`, `.exists()`) and raise a specific `ProthonError` subclass with an actionable message when the check fails. Used in 12+ locations across the codebase.

*Positive guard* — verify the resource exists before acting. Guard functions accept a `Path`, call `.is_dir()` / `.is_file()` / `.exists()`, and proceed only when the check passes.

*Negative guard* — verify the resource does NOT exist, then fail fast by raising a domain-specific `ProthonError` subclass such as `ProjectNotFoundError` or `ProjectAlreadyInitError` with an actionable message.

**When to use:** Before any filesystem read, write, copy, or iteration that semantically requires the path to be present (or absent). Skip for idempotent operations like `mkdir(parents=True, exist_ok=True)`.

**Rationale:** Fail fast at the boundary rather than deep inside I/O routines; raise domain-specific errors (`ProjectNotFoundError`, `ProjectAlreadyInitError`) that flow through the centralized CLI error boundary with actionable messages.

### File I/O Error Handling Pattern

File I/O operations that read from or write to the filesystem — using methods like `Path.read_text()`, `Path.write_text()`, `Path.read_bytes()`, `Path.write_bytes()`, or `open()` — are wrapped in try/except blocks catching `OSError` and `UnicodeDecodeError`. Rather than propagating OS-level failures upward, the handler returns a safe default value appropriate to the calling context: `None` for optional single-result lookups, an empty string for content-extraction routines, an empty list for collection-returning scanners, or simply continues to the next item in an iteration loop. This pattern appears in 15 locations across 12 modules (`versioning.py`, `adoption.py`, `ast_miner.py`, `config.py`, `commands.py`, `promise.py`, `checks/adoption.py`, `checks/utils.py`, `refactor/metrics.py`, `refactor/testability.py`, `refactor/discovery.py`).

**When to use:** Whenever a function reads or writes a file whose existence or encoding cannot be guaranteed by a prior guard — for example, iterating over a directory of source files, loading a configuration file that may be missing or malformed, or hashing a file that may have been deleted between the existence check and the read. Do not use this pattern when the Path Existence Guard Pattern already validates the path and a missing file should be a hard failure.

**Rationale:** OS-level errors (permission denied, file vanished mid-scan, broken symlink, unexpected encoding) are routine in batch filesystem operations, especially when scanning large directory trees. Silently degrading to a safe default keeps the caller's control flow simple and avoids cascading failures in collection-oriented operations where one bad file should not abort the entire scan. The pattern complements the Path Existence Guard Pattern: guards handle expected preconditions at the boundary, while this pattern handles unexpected failures during the I/O operation itself.

## Error Handling

### Centralized CLI Error Boundary

The `cli.py` module acts as the single catch-all boundary for `ProthonError` and its subclasses. Library modules raise exceptions; the CLI catches them, presents a formatted message, and terminates with a non-zero exit code.

### Terminal Failure Pattern

When a subagent reaches `max_attempts` for a task without passing verification and quality gates, it reports a terminal failure. The orchestrator records the failure and asks the user for a decision (skip, retry, or abort) to prevent infinite loops. As a programmatic backstop independent of skill-prompt compliance, `record_attempt()` enforces the `max_attempts` limit by raising `MaxAttemptsExceeded` (a subclass of `PromiseError`) when `attempts >= max_attempts`, preventing the counter from incrementing further.

### Data-Driven Doc Consistency Failures

Contradictions found by the `doc-harmonizer` are treated as data, not exceptions. They are presented as a structured report of `Conflict` objects, enabling interactive resolution and approval before any documents are amended.

### Model/Provider Resolution Errors

Configuration resolution for `opencode` enforces that both model and provider must be present if one is provided. Violations raise a `ProthonError` explaining the required format, ensuring early failure.

## Testing Patterns

### Test Value Over Test Count

Prioritize fewer, higher-value tests over comprehensive coverage. Not every line needs a test.

**Do NOT test:**
- Trivial code: simple attribute access, getters/setters, one-line assignments, pass-through functions that just delegate
- Language features: that `+` adds numbers, that `dict[key]` retrieves values, that `if` branches
- Framework behavior: that FastAPI routes return responses, that Pydantic validates types, that Typer parses CLI args
- Redundant coverage: the same conditional logic tested at unit, integration, and e2e levels with identical assertions
- Implementation details: private `_helper` methods already exercised through public method tests

**Focus tests on:**
- Business logic: conditional branches, calculations, state transitions, multi-step workflows
- Edge cases: boundary conditions, error handling paths, malformed input handling
- Integration points: how components interact, protocol compliance, contract boundaries
- Invariants: properties that must always hold regardless of input

**Test file organization:** One test file per source module is NOT required. Test files map to cohesive units of behavior, not file names. A complex module may warrant multiple test files (`test_auth_flows.py`, `test_auth_edge_cases.py`); a trivial module with no logic may need no test file at all.

### Lightweight, Fast Tests

Tests must be cheap to run. The full suite should complete in seconds, not minutes.

**Keep tests lightweight:**
- Use fakes/stubs instead of real services (no database connections, no HTTP servers, no filesystem writes to real paths)
- Prefer in-memory structures: `io.StringIO` over temp files, `dict` over real caches, `FakeGitDiff` over subprocess calls
- Avoid loading heavy dependencies in unit tests — mock at the boundary
- Isolate units so each test exercises one module, not the entire dependency graph
- Reset state between tests; never rely on test execution order

**Fast test patterns:**
- Protocol fakes over real implementations (see Protocol Fakes Over Mocks)
- Fixture scope: use `@pytest.fixture(scope="function")` as default; promote to session/class only when setup is expensive and stateless
- Skip slow tests by default: mark with `@pytest.mark.slow` and run via `pytest -m "not slow"` in CI fast paths
- Parallel-safe: structure tests so `pytest-xdist` works (no shared mutable state between tests)

### Protocol Fakes Over Mocks

Test dependencies are managed using simple fake implementations that satisfy protocols (e.g., `FakeGitDiff` for `GitDiffProvider`). This ensures tests break when interfaces change and avoids fragile standard mocks.

### Subagent Mocking Pattern

Orchestration logic is tested using a `FakeAssistantBackend` that simulates subagent responses, return codes, and file modifications. This enables exhaustive testing of retry loops and decision-making without hitting real APIs.

### Conflict Injection Pattern

The `doc-harmonizer` is verified by injecting known contradictions between SPEC, DESIGN, and PATTERNS. Tests confirm the harmonizer detects the conflict, identifies the higher-authority document, and proposes the correct resolution.

### Concurrency Stress Testing

The `.toml.lock` exclusive locking mechanism is verified using multiprocessing to simulate concurrent subagents. Tests ensure all updates are serialized and no data is lost.
