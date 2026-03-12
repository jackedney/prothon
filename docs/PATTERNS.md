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

### File Locking and Atomic Persistence

When parallel subagents mark tasks complete simultaneously, the promise TOML file is a shared resource. `complete_task()` wraps its load → modify → save cycle in an exclusive file lock to prevent lost updates. `save_promise()` writes atomically via `tempfile.mkstemp` + `os.fsync` + `os.replace`, so readers never see partially-written content — read-only operations (`status`, `check_task`, `plan`) are safe without locking.

The lock implementation is cross-platform: `fcntl.flock` on Unix, `msvcrt.locking` on Windows. The lock uses a sibling `.toml.lock` file (not the TOML itself) so the promise file can be fully rewritten without interfering with the lock. `complete_task()` runs verification (read-only, no lock needed due to atomic writes) before acquiring the exclusive lock for the read-modify-write cycle.

```python
@contextmanager
def _lock_promise(path: Path) -> Iterator[None]: ...
```

### Guard-Clause Preconditions

Domain functions that require specific environmental conditions validate them upfront and raise domain exceptions. Guards come first, happy path follows. No nested `if/else` trees. For example, `init_existing()` checks for a git repository and the absence of `docs/SPEC.md` before proceeding. This keeps validation in the domain layer (not the CLI) and follows the "raise at source" error handling pattern.

### Inline Content Constants

Doc scaffolds, CI workflow templates, and agent instruction content are inlined as `_UPPER_SNAKE` module-level constants in `scaffold.py` rather than read from the Copier template at runtime. This decouples `init` from Copier's file layout — template restructuring cannot break init.

### Idempotent Symlink Creation

Both `scaffold.py` and `skills.py` create symlinks. The pattern is: remove stale target (symlink or real directory), then create. This ensures re-running is safe. `scaffold.py` uses relative symlinks for portability within a repo. `skills.py` uses absolute symlinks because the source is outside the project tree.

### XDG_CONFIG_HOME Resolution

Backends and configuration readers that access user-level directories respect `$XDG_CONFIG_HOME` with a `~/.config` fallback. Empty or relative values fall back to `~/.config` to avoid syncing into repo-relative paths. This applies to `OpenCodeBackend.sync_skills()` and the config resolution functions in `cli.py`.

### Rich Table Rendering as Private Helpers

`cli.py` builds tables via private `_render_*` functions that return `Table` objects. Commands print them. This separates rendering logic from I/O. Status styling uses a dict mapping `CheckStatus` enum values to `(label, style)` tuples to avoid branching.

```python
def _render_plan(p: Promise) -> Table: ...
def _render_status(p: Promise) -> Table: ...
def _render_check_report(report: TaskCheckReport) -> Table: ...
```

### Per-Command Agent Option with Annotated Type

The `--agent`/`-a` flag is per-command, defined once as a shared `Annotated` type and added to each command that launches an assistant session. The value flows explicitly through `_launch_skill` → `resolve_agent` as a function parameter — no module-level mutable state.

```python
AgentOption = Annotated[
    str | None,
    typer.Option(
        "--agent", "-a",
        envvar="PROTHON_AGENT",
        help="AI agent backend (claude-code, opencode)",
    ),
]
```

### Per-Command Model/Provider Options with Annotated Types

The `--model`/`-m` and `--provider`/`-p` flags follow the same pattern — shared `Annotated` types added to each session command. These are opencode-specific (Claude Code silently ignores them).

```python
ModelOption = Annotated[
    str | None,
    typer.Option(
        "--model", "-m",
        envvar="PROTHON_MODEL",
        help="Model name (opencode only)",
    ),
]

ProviderOption = Annotated[
    str | None,
    typer.Option(
        "--provider", "-p",
        envvar="PROTHON_PROVIDER",
        help="Provider name (opencode only)",
    ),
]

@app.command()
def spec(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None: ...
```

### Fallthrough Precedence Chain

`resolve_agent()` and `_resolve_config_value()` implement multi-level precedence chains where the first non-empty value wins. Each level is a simple guard with fallthrough to the next. The chain lives in `cli.py` because levels 3-4 read config files — these are CLI concerns, not backend concerns.

### Model/Provider Join Rule

`resolve_model()` resolves model and provider independently via the same precedence chain, then joins them into opencode's required `provider/model` format. If `--model` already contains `/`, it's treated as a complete specifier. If only one resolves, the function raises an error. If neither resolves, it returns `None` to defer to opencode's defaults.

### CLI Guard and Launch Helpers

Repeated "find-or-exit" and "resolve-launch-or-exit" logic is extracted into private helpers that catch domain exceptions and raise `typer.Exit`. `_launch_skill` also handles doc commitment and follow-up triggers.

```python
def _launch_skill(
    skill_name: str,
    cwd: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    run_follow_ups: bool = True,
) -> None: ...
```

### Interactive Prompt with Validation Loop

`prothon new` collects inputs via `typer.prompt()` with while-loop validation for constrained fields. This pattern ensures user input is re-requested until it meets project requirements without needing external validation libraries.

```python
def _collect_project_details() -> dict: ...
```

### Conditional Path Branching in Domain Functions

`init_existing()` branches on whether `pyproject.toml` exists to decide whether to scaffold via Copier or skip it. Convergence on a common overlay follows the guard-first, branch-after pattern for clean control flow.

```python
def init_existing(cwd: Path | None = None) -> list[Path]: ...
```

### Lazy Imports for Heavy Dependencies

Heavy packages like Copier are imported inside the function body to minimize import-time overhead for lightweight CLI operations. This pattern is an intentional exception to standard import order for performance.

### Versioning as Pure Functions

Semver arithmetic is implemented using pure functions that handle parsing, bumping, and returning new version strings. File updates are handled by specific functions that preserve formatting (tomlkit) or perform regex replacement, maintaining a stateless and testable versioning core.

### SPEC.md Tamper Detection

`_launch_skill()` implements a SHA-256 hash comparison of `docs/SPEC.md` before and after sessions to warn of unauthorized modifications. This soft guard complements skill-level edit restrictions.

### CI Workflow Patterns

CI workflow templates are inlined as private module-level constants in `scaffold.py`, decoupling project initialization from the Copier template layout and maintaining a self-contained adoption logic.

## Skill Authoring Patterns

### Frontmatter Conventions

All bundled skills live in `src/prothon/skills/` as directories containing a `SKILL.md`. Frontmatter fields vary by skill type:

| Field | User-facing session skills | Subagent-mode skills |
|-------|---------------------------|---------------------|
| `name` | Required | Required |
| `description` | Required | Required |
| `model` | Omitted — user's assistant selection applies | `sonnet` — cost-effective for automated analysis |
| `context` | Omitted — runs in user's session | `fork` — isolates subagent context |

### Skill Structure

Standard sections follow a mandatory sequence: `## Role`, `## Prerequisites`, `## Focus` (optional), `## Process`, `## Guards`, `## Output`, and `## After Writing`. This ensures consistent behavior and authority enforcement across all prothon agents.

### Subagent Spawning

Skills spawning subagents must use canonical agent type names (`general-purpose`, `explore`, `plan`) and a standardized instruction format. This enables cross-assistant compatibility by letting each backend translate the canonical request into its native tool call.

### Conversational Cadence

User-facing doc-writer skills enforce a one-message-then-wait cadence. This prevents context dumping and ensures incremental user control over design and requirements decisions.

### Documentation Safety in Skills

Non-doc agents explicitly declare `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` as read-only. Skills that are authorized to write to documentation files must perform a local git commit immediately after writing to prevent accidental state loss.

### CLI References in Skills

Skills must only refer to CLI commands (e.g., `prothon design`), never backend-specific skill names or slash commands, keeping implementation details hidden from the user.

### Generated Reference Skills

The tech-researcher generates project-specific reference guides in `.agents/skills/`. These use a simplified structure and are marked as non-interactive to provide context-efficient domain knowledge to other agents.

## Error Handling

### Custom Exception Hierarchy

A flat hierarchy under `ProthonError` in `exceptions.py` provides domain-specific failure modes. Callers catch specific subclasses to handle expected failures gracefully.

### Raise at Source, Catch at Boundary

Domain modules raise exceptions at the point of failure without printing or exiting. `cli.py` serves as the single boundary for catching `ProthonError` and presenting formatted error messages to the user.

### Subprocess Error Wrapping

The `run_git()` helper converts raw `subprocess` failures into `GitError`, providing a typed and consistent interface for git operations across the project.

## Testing Patterns

### Test Layout

The `tests/` directory mirrors the `src/prothon/` layout, with one test file per module. Shared fixtures, fakes, and factories are centralized in `conftest.py`.

### Protocol Fakes Over Mocks

Test dependencies are managed using simple fake implementations that satisfy protocols like `GitDiffProvider`. This ensures tests break when interfaces change, providing better safety than standard mocks.

### Fixture Conventions

Tests utilize `tmp_path` for filesystem isolation and factory functions in `conftest.py` for flexible test data construction, ensuring tests only specify the data relevant to the scenario being verified.

### CLI Integration Tests

Typer's `CliRunner` is used for in-process command testing, providing fast and isolated verification of CLI behavior and output without the overhead of external subprocesses.

### Versioning Tests

Versioning is verified across three levels: unit tests for semver arithmetic, filesystem tests for formatting preservation, and repository-based tests for correct bump type detection.
