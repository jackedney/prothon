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
def complete_task(task_index: int, *, attempts: int = 1, diff: GitDiffProvider | None = None, path: Path = PROMISE_PATH) -> None: ...
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

Use `@dataclass` with `field(default_factory=...)` for mutable defaults. Dataclasses carry data and may expose computed properties, but should not contain complex business logic. The promise system uses this for `Task`, `Metadata`, `Promise`, `CheckResult`, `FileCheckDetail`, and `TaskCheckReport`. The `TaskCheckReport.passed` property is an example of a lightweight computed property on a data carrier.

### Protocols for Dependency Injection

Use `typing.Protocol` where a module needs a swappable capability — primarily for testing. Protocols provide structural typing without inheritance. Implementations satisfy the contract structurally without inheriting from the protocol.

Two protocols exist in the codebase:

`GitDiffProvider` declares `diff_names(base_commit: str) -> set[str]` and `diff_numstat(base_commit: str) -> DiffStat`. It enables subprocess-free testing of promise verification.

`AssistantBackend` declares read-only properties `name -> str`, `cli_command -> str`, and `install_hint -> str`, plus methods `build_command(skill_name: str, cwd: Path, model: str | None = None) -> list[str]`, `sync_skills() -> None`, `env_overrides() -> dict[str, str]`, and `subagent_type_map() -> dict[str, str]`. It enables pluggable assistant backends with a shared launch lifecycle.

### Registry for Backend Lookup

A module-level dict maps string names to backend classes. A `register_backend()` function provides a public extension hook for programmatic use and testing. `get_backend()` instantiates by name, listing all registered backends in the error message when the name is unknown.

### Shared Lifecycle as Standalone Function

The `launch()` function accepts anything satisfying `AssistantBackend` and runs the shared lifecycle: binary existence check via `shutil.which()`, skill syncing, environment merging, subprocess execution, and return code reporting. Shared behavior lives in a function, not a base class — this follows the functions-first default and keeps protocols as pure interfaces.

### Default Arguments for Production, Parameters for Testing

Functions use production defaults (e.g., `path: Path = PROMISE_PATH`) but accept overrides so tests never touch real state and never need monkeypatching. This applies to all promise functions, git functions, and skill sync.

### File Locking for Concurrent Access

When parallel subagents mark tasks complete simultaneously, `complete_task()` wraps its load-modify-save cycle in an exclusive file lock using `fcntl.flock` on a sibling `.toml.lock` file. The lock file is separate from the TOML file so the promise can be fully rewritten without interfering with the lock. Only write operations need locking — read-only operations are safe without it.

### Guard-Clause Preconditions

Domain functions that require specific conditions validate them upfront and raise domain exceptions. Guards come first, happy path follows. No nested `if/else` trees. This applies to `init_existing()` (git repo check, existing SPEC check), `check_task()` (index bounds), and `complete_task()` (verification before marking complete).

### Inline Content Constants

Doc scaffolds, CI workflow templates, and agent instruction content are inlined as `_UPPER_SNAKE` module-level constants in `scaffold.py` rather than read from the Copier template at runtime. This decouples `init` from Copier's file layout — template restructuring cannot break init.

### Idempotent Symlink Creation

Both `scaffold.py` and `skills.py` create symlinks. The pattern is: remove stale target (symlink or real directory), then create. This ensures re-running is safe. `scaffold.py` uses relative symlinks for portability within a repo. `skills.py` uses absolute symlinks because the source is outside the project tree.

### XDG_CONFIG_HOME Resolution

Backends and configuration readers that access user-level directories respect `$XDG_CONFIG_HOME` with a `~/.config` fallback. Empty or relative values fall back to `~/.config` to avoid syncing into repo-relative paths. This applies to `OpenCodeBackend.sync_skills()` and the config resolution functions in `cli.py`.

### Rich Table Rendering as Private Helpers

`cli.py` builds tables via private `_render_*` functions that return `Table` objects. Commands print them. This separates rendering logic from I/O. Status styling uses a dict mapping enum values to label/style tuples to avoid branching.

### Per-Command Options with Annotated Types

The `--agent`, `--model`, and `--provider` flags are per-command, defined once as shared `Annotated` types (`AgentOption`, `ModelOption`, `ProviderOption`) and added to each command that launches an assistant session. Values flow explicitly through `_launch_skill()` as function parameters — no module-level mutable state. Typer's `envvar=` parameter handles environment variable resolution.

### Fallthrough Precedence Chain

`resolve_agent()` and `_resolve_config_value()` implement multi-level precedence chains where the first non-empty value wins. Each level is a simple guard with fallthrough to the next. The chain lives in `cli.py` because levels 3-4 read config files — these are CLI concerns, not backend concerns.

### Model/Provider Join Rule

`resolve_model()` resolves model and provider independently via the same precedence chain, then joins them into opencode's required `provider/model` format. If `--model` already contains `/`, it's treated as a complete specifier. If only one resolves, the function raises an error. If neither resolves, it returns `None` to defer to opencode's defaults.

### CLI Guard and Launch Helpers

Repeated "find-or-exit" and "resolve-launch-or-exit" logic is extracted into private helpers (`_require_project_root()`, `_require_doc()`, `_require_promise_file()`, `_launch_skill()`) that catch domain exceptions and raise `typer.Exit`. All five assistant commands delegate to `_launch_skill()`.

### Lazy Imports for Heavy Dependencies

Copier is imported inside the function body, not at module level, to avoid loading it and its transitive dependencies when the module is imported for lightweight operations. This is an intentional exception to the standard import order — use it only for genuinely heavy packages.

### Versioning as Pure Functions

Semver arithmetic uses pure functions with no external library — parse, bump major/minor/patch, return new string. File update functions are split: one for `pyproject.toml` (tomlkit preserves formatting) and one for `__init__.py` (regex replacement). Change detection takes before/after SHAs and returns the bump type based on which doc files changed.

### SPEC.md Tamper Detection

`_launch_skill()` computes a SHA-256 hash of `docs/SPEC.md` before launching any non-spec-writer skill and compares it after the session completes. If the hash differs, a warning is emitted. This is a soft guard complementing the skill-level edit restrictions — it detects accidental SPEC modification by agents that shouldn't be writing to it.

### Pattern Summary

| Pattern | Where | Why |
|---------|-------|-----|
| Plain functions | Default for all modules | Simplest unit, easiest to test |
| Dataclasses | Data carriers (`Promise`, `CheckResult`, `Task`) | Typed, immutable-friendly, no boilerplate |
| Protocols | DI boundaries (`GitDiffProvider`, `AssistantBackend`) | Structural typing, swappable for testing |
| Standalone function | Shared lifecycle (`launch()`) | Keeps protocols as pure interfaces |
| Registry dict | Backend lookup by name | Explicit, debuggable, extensible |
| Default args | Production vs test paths | Avoids monkeypatching |
| Guard clauses | Domain preconditions | Fail fast, no nested conditionals |
| Inline constants | Doc scaffolds, CI workflows | Decouples init from Copier layout |
| Idempotent symlinks | `scaffold.py`, `skills.py` | Safe re-runs |
| Lazy imports | Copier in `scaffold.generate()` | Avoid heavy import on lightweight paths |
| Rich table helpers | `_render_*` in `cli.py` | Separate rendering from I/O |
| Annotated types | Per-command CLI options | Explicit data flow, no global state |
| Fallthrough precedence | Config resolution functions | First non-empty value wins |
| SPEC tamper detection | `_launch_skill()` | Soft guard against accidental SPEC writes |

## Error Handling

### Custom Exception Hierarchy

Flat hierarchy under a single base in `exceptions.py`. No deep inheritance trees. Each exception maps to one failure domain.

`ProthonError` is the base exception. Subclasses — `ProjectNotFoundError`, `ProjectAlreadyInitError`, `PromiseError`, `AssistantNotFoundError`, `UnknownBackendError`, `ComplianceError`, `GitError`, `VersionError` — each map to one failure domain. `ProthonError` is the catch-all at the CLI boundary. Specific subclasses allow callers to handle individual failure modes when needed, but the CLI only needs to catch the base.

### Raise at Source, Catch at Boundary

Domain modules raise specific exceptions at the point of failure. `cli.py` is the only place that catches `ProthonError` and converts it to a user-facing message with a non-zero exit code. Domain modules never call `sys.exit()` or print errors — they raise and let the boundary handle presentation.

### No Bare Exceptions, No Silent Swallowing

Always catch the specific failure type. Re-raise as a domain exception with context about what went wrong. Never catch `Exception` and return `None` — this hides bugs.

### Subprocess Error Wrapping

All git interaction goes through `run_git()` which converts `subprocess` failures into `GitError` immediately. Callers never see raw `subprocess.CalledProcessError`. The environment includes `GIT_TERMINAL_PROMPT=0` to prevent interactive auth prompts from hanging the process.

When the original traceback adds noise rather than clarity, use `from None` to suppress exception chaining — for example, when re-raising a `GitError` with a more descriptive message like "not a git repository."

### Error Message Convention

Lowercase, specific, include the value that caused the problem. Examples: `"task index 5 out of range (0-3)"`, `"no backend registered for 'foo' (available: claude-code, opencode)"`, `"invalid version format: 'abc'"`. This makes messages greppable and self-diagnosing.

## Testing Patterns

### Test Layout

Mirror the source tree under `tests/`, one test file per module.

```
tests/
    conftest.py          # shared fixtures, fakes, factories
    test_project.py      # project root detection
    test_git.py          # git wrapper, SubprocessGitDiff
    test_skills.py       # skill discovery and symlink sync
    test_scaffold.py     # init_existing, generate, Copier integration
    test_promise.py      # promise model, verification
    test_assistant.py    # backend protocol, registry, launch
    test_versioning.py   # semver, file updates, change detection
    test_cli.py          # integration tests via Typer CliRunner
```

### Naming

- **Files:** `test_{module}.py`
- **Functions:** `test_{function}_{scenario}` — descriptive enough to diagnose failures from the name alone
- **No test classes** unless shared setup can't be handled by fixtures

### Protocol Fakes Over Mocks

Write simple fake implementations that satisfy protocols. Fakes are real code — they break when the protocol changes. Mocks don't. A `FakeGitDiff` in `conftest.py` accepts canned `names` and `stats` data, satisfying `GitDiffProvider` structurally. Reserve `unittest.mock` for cases where you genuinely can't control the dependency (e.g., patching `shutil.which`). Prefer restructuring to make fakes possible.

### Fixture Conventions

- `tmp_path` (built-in) for any test that touches the filesystem
- Shared fakes and factories in `conftest.py`
- **Factories over static fixtures** — functions with sensible defaults and keyword overrides for constructing test data like tasks and promises. Override only what the test cares about.

### Guard Clause Tests

Each precondition in a domain function gets a dedicated test. Use `tmp_path` to create the exact failing condition, assert the specific exception type and message. One test per guard, name encodes the failing condition (`_raises_when_{condition}`).

### Filesystem Assertion Helpers

Adoption creates files, directories, and symlinks. Keep happy-path tests readable with simple helpers in `conftest.py` — for example, an `assert_symlink_to` helper that checks both that a path is a symlink and that it points to the expected target.

### Idempotency and Non-Destructiveness Tests

Since R17 requires `init` must not modify existing files, test that pre-existing content survives. Write content to a file before calling `init_existing()`, then assert the original content is still present afterward.

### Hypothesis for Boundary Logic

Use Hypothesis for functions with numeric or string boundaries — tolerance checks, version parsing, TOML roundtrips. Don't use Hypothesis for everything — plain `parametrize` is clearer for known edge cases.

### CLI Integration Tests

Test CLI commands via Typer's `CliRunner`, not subprocess. Fast and in-process. Use `monkeypatch.chdir(tmp_path)` to isolate the working directory. Assert on exit codes and output content.

### Versioning Tests

Three levels: (1) unit tests for semver arithmetic as direct function calls with no filesystem, (2) file update tests using `tmp_path` to verify tomlkit preserves comments and regex replacement works, (3) change detection tests using `run_git` with temp repos to verify the correct bump type for different file changes.

### What Not to Test

- Third-party library behavior (Typer routing, tomlkit parsing)
- Trivial dataclass construction
- Private helpers — unless they contain non-obvious logic (like `_within_tolerance`)
