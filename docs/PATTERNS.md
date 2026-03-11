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
) -> None:
    root = _require_project_root()
    _launch_skill("prothon-spec-writer", root, agent, model=model, provider=provider)
```

This allows natural usage like `prothon spec --agent opencode --model glm-5 --provider z-ai`. Typer's `envvar=` parameter handles env var resolution on each command automatically.

### Fallthrough Precedence Chain

`resolve_agent()` and `_resolve_config_value()` implement multi-level precedence chains where the first non-empty value wins. Each level is a simple guard with fallthrough to the next. The chain lives in `cli.py` because levels 3-4 read config files — these are CLI concerns, not backend concerns.

### Model/Provider Join Rule

`resolve_model()` resolves model and provider independently via the same precedence chain, then joins them into opencode's required `provider/model` format. If `--model` already contains `/`, it's treated as a complete specifier. If only one resolves, the function raises an error. If neither resolves, it returns `None` to defer to opencode's defaults.

### CLI Guard and Launch Helpers

Repeated "find-or-exit" and "resolve-launch-or-exit" logic is extracted into private helpers that catch domain exceptions and raise `typer.Exit`. Keeps command bodies clean.

```python
def _require_project_root() -> Path:
    try:
        return find_project_root()
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

def _require_promise_file(root: Path) -> Path:
    promise_path = root / promise.PROMISE_PATH
    if not promise_path.exists():
        typer.echo(f"No promise file found at {promise_path}")
        raise typer.Exit(1)
    return promise_path

def _launch_skill(
    skill_name: str, cwd: Path, agent: str | None = None,
    model: str | None = None, provider: str | None = None,
) -> None:
    """Resolve backend, launch skill, handle errors."""
    try:
        name = resolve_agent(agent)
        backend = get_backend(name)
        resolved_model = resolve_model(model, provider) if name == "opencode" else None
        rc = launch(backend, skill_name, cwd, model=resolved_model)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
```

`_launch_skill()` is the single call site for the resolve → get → launch chain. All five assistant commands (`spec`, `design`, `patterns`, `execute`, `compliance`) delegate to it.

### Interactive Prompt with Validation Loop

`prothon new` collects inputs via `typer.prompt()` with while-loop validation for constrained fields. No validation library — just re-prompt until acceptable.

```python
python_version = typer.prompt("Python version (3.11/3.12/3.13)", default="3.13")
while python_version not in ("3.11", "3.12", "3.13"):
    typer.echo("Must be 3.11, 3.12, or 3.13")
    python_version = typer.prompt("Python version (3.11/3.12/3.13)", default="3.13")
```

### Conditional Path Branching in Domain Functions

`init_existing()` branches on whether `pyproject.toml` exists — Path A (absent) scaffolds via Copier, Path B (present) skips it. Both paths converge on the common overlay. Guards come first, branching after.

```python
def init_existing(cwd: Path | None = None) -> list[Path]:
    root = Path(cwd) if cwd else Path.cwd()
    # Guards first
    ...
    # Branch on project state
    if not (root / "pyproject.toml").exists():
        answers = _collect_project_details()
        _run_copier_init(root, answers)
    # Common overlay (both paths)
    ...
```

### Lazy Imports for Heavy Dependencies

Copier is imported inside the function body, not at module level, to avoid loading it and its transitive dependencies when the module is imported for lightweight operations. This is an intentional exception to the standard import order — use it only for genuinely heavy packages.

### Versioning as Pure Functions

Semver arithmetic uses pure functions with no external library — parse, bump major/minor/patch, return new string. File update functions are split: one for `pyproject.toml` (tomlkit preserves formatting) and one for `__init__.py` (regex replacement). Change detection takes before/after SHAs and returns the bump type based on which doc files changed. Priority: `docs/SPEC.md` → major, `docs/DESIGN.md` → minor, `docs/PATTERNS.md` or `src/` → patch, otherwise `None`.

### SPEC.md Tamper Detection

`_launch_skill()` computes a SHA-256 hash of `docs/SPEC.md` before launching any non-spec-writer skill and compares it after the session completes. If the hash differs, a warning is emitted. This is a soft guard complementing the skill-level edit restrictions — it detects accidental SPEC modification by agents that shouldn't be writing to it.

### CI Workflow Patterns

CI workflow templates (GitHub Actions version-bump and version-tag, GitLab CI version-bump) are inlined as `_UPPER_SNAKE` module-level constants in `scaffold.py`, following the same pattern as doc scaffolds. This keeps the `template/` directory focused on Copier template files and decouples `init` from Copier's layout.

### Pattern Summary

| Pattern | Where | Why |
|---------|-------|-----|
| Plain functions | Default for all modules | Simplest unit, easiest to test |
| Dataclasses | Data carriers (`Promise`, `CheckResult`, `Task`) | Typed, immutable-friendly, no boilerplate |
| Protocols | DI boundaries (`GitDiffProvider`, `AssistantBackend`) | Structural typing, swappable for testing |
| Standalone function | Shared lifecycle (`launch()`) | Keeps protocols as pure interfaces |
| Registry dict | Backend lookup by name | Explicit, debuggable, extensible |
| Default args | Production vs test paths | Avoids monkeypatching |
| Guard clauses | Domain precondition validation (`init_existing()`) | Fail fast, domain exceptions, no nested conditionals |
| Inline constants | Doc scaffolds, CI workflows in `scaffold.py` | Decouples init from Copier template layout |
| Idempotent symlinks | `scaffold.py`, `skills.py` | Safe re-runs, stale link cleanup |
| Lazy imports | Copier in `scaffold.generate()` | Avoid heavy import for lightweight code paths |
| Rich table helpers | `_render_*` in `cli.py` | Separate rendering from I/O, enum-to-style dicts avoid branching |
| CLI guard/launch helpers | `_require_project_root()`, `_require_promise_file()`, `_launch_skill()` | Extract repeated find-or-exit and resolve-launch-or-exit into reusable helpers |
| Per-command option + `Annotated` type | `--agent`/`-a` on each session command via shared `AgentOption` | Explicit data flow, no module-level state, natural CLI usage |
| Per-command model/provider options | `--model`/`-m`, `--provider`/`-p` on each session command via shared `ModelOption`, `ProviderOption` | Explicit data flow, opencode-specific, silently ignored by Claude Code |
| Fallthrough precedence | `resolve_agent(cli_value)` 5-level chain | First non-empty value wins; each level is a guard with fallthrough |
| Model/provider join rule | `resolve_model(cli_model, cli_provider)` | opencode requires `provider/model` format; supports both separate flags and combined format |
| XDG_CONFIG_HOME resolution | `OpenCodeBackend.sync_skills()`, `resolve_agent()` | Respect user's XDG override with `~/.config` fallback |
| Prompt validation loops | `prothon new` constrained inputs | Simple while-loop re-prompt, no validation library |
| Conditional path branching | `init_existing()` Path A/B | Guards first, branch on state, converge on common overlay |
| Separate input collection | `new` in `cli.py` vs `_collect_project_details()` in `scaffold.py` | `new` uses Typer prompts directly (CLI concern); `_collect_project_details()` is only for `init_existing` Path A. Intentionally not shared — different UX contexts. |
| Semver pure functions | `versioning.py` bump functions | Zero dependencies, ~30 lines, full control over format |
| SPEC tamper detection | `_launch_skill()` | Soft guard against accidental SPEC writes |

## Skill Authoring Patterns

### Frontmatter Conventions

All bundled skills live in `src/prothon/skills/` as directories containing a `SKILL.md`. Frontmatter fields vary by skill type:

| Field | User-facing session skills | Subagent-mode skills |
|-------|---------------------------|---------------------|
| `name` | Required | Required |
| `description` | Required | Required |
| `model` | Omitted — user's assistant selection applies | `sonnet` — cost-effective for automated analysis |
| `context` | Omitted — runs in user's session | `fork` — isolates subagent context |

**User-facing session skills** (spec-writer, design-writer, patterns-writer, execute): launched by the user via `prothon <command>`, run interactively. No `model` or `context` frontmatter — the user controls which assistant and model they use.

**Subagent-mode skills** (compliance-checker, doc-harmonizer, tech-researcher): spawned programmatically by other skills, run autonomously. Set `model: sonnet` and `context: fork` to control cost and isolation.

```yaml
---
name: prothon-doc-harmonizer
description: Cross-reference SPEC, DESIGN, and PATTERNS for conflicts
model: sonnet
context: fork
---
```

Note: `model` and `context` are Claude Code extensions — opencode silently ignores them. Skills must not depend on these fields for correct behavior. Any skill that needs subagent isolation must use the explicit "Spawn a subagent" instruction pattern instead.

### Skill Structure

Standard sections in order. Not all skills need every section, but those present follow this sequence:

1. **`## Role`** — One-sentence identity statement. What the skill is and does.
2. **`## Prerequisites`** — Guard conditions checked before proceeding (e.g., which docs must exist). Directs the user to the correct CLI command if preconditions fail.
3. **`## Focus`** — Optional. Priorities and principles that guide the skill's decisions.
4. **`## Process`** — The bulk of the skill. Numbered steps, possibly with Path A / Path B branching (e.g., new vs update workflows for doc-writers).
5. **`## Guards`** — Explicit prohibitions — what the skill must refuse to do. Enforces separation of concerns and doc authority.
6. **`## Output`** — What the skill produces when complete.
7. **`## After Writing`** — Quality gates that run post-write: commit the file, launch harmonizer subagent, etc.

```markdown
## Role
You are the Design Writer. ...

## Prerequisites
- `docs/SPEC.md` must exist and be populated
- If missing, refuse and direct the user to run `prothon spec`

## Process
### Path A: New Design (DESIGN.md is empty)
...
### Path B: Updating Existing Design (DESIGN.md has content)
...

## Guards
You MUST refuse to include anything that contradicts SPEC.md.

## Output
A populated `docs/DESIGN.md` with all sections filled in.

## After Writing
1. Commit: `git add docs/DESIGN.md && git commit -m "docs: update DESIGN.md via design-writer"`
2. Launch doc-harmonizer subagent.
```

### Subagent Spawning

Skills that need to spawn subagents use canonical agent type names from the DESIGN's subagent type mapping table. The instruction format is:

```
Spawn a subagent (type: general-purpose, fresh context) with this prompt:
"Activate the prothon-<skill-name> skill and execute it. ..."
```

Skills must NOT reference tool-specific APIs (e.g., `Task tool, subagent_type: general-purpose` for Claude Code, or `task` tool for opencode). Each assistant's LLM translates the canonical instruction into its native tool call. The canonical names are:

| Canonical name | Use case |
|---------------|----------|
| `general-purpose` | Quality gate subagents (harmonizer, compliance, tech-researcher) |
| `explore` | Codebase exploration |
| `plan` | Implementation planning |

Subagent prompts should be self-contained — include enough context for the subagent to operate without reading the parent skill's conversation history. Always specify "fresh context" to ensure a clean slate.

### Conversational Cadence

User-facing doc-writer skills (spec-writer, design-writer, patterns-writer) enforce strict one-message-then-wait cadence:

- Send ONE section or question per message, then STOP and wait for the user's response
- Use plain text output — do NOT use the `AskUserQuestion` tool
- Every message should end with an implicit or explicit "what do you think?"
- Never dump all decisions or sections at once

This ensures the user stays in control of design decisions and can steer direction incrementally.

### Documentation Safety in Skills

**Read-only guards** — Non-doc agents (execute, compliance-checker, tech-researcher) explicitly declare in their Guards section that `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` are read-only and must not be written to.

**Commit-after-write** — Every skill that writes to a documentation file commits immediately after writing:

```bash
git add docs/<FILE>.md
git commit -m "docs: update <FILE>.md via <skill-name>"
# Do NOT push — local commit only
```

This prevents subsequent agent sessions from accidentally overwriting uncommitted changes.

**Permitted writers per file:**

| File | Permitted writers |
|------|-------------------|
| `docs/SPEC.md` | spec-writer only |
| `docs/DESIGN.md` | design-writer, doc-harmonizer (with user approval) |
| `docs/PATTERNS.md` | patterns-writer, doc-harmonizer (with user approval) |

### CLI References in Skills

Skills tell users to run CLI commands, never skill slash commands. Users should not need to know about the skill layer.

```
# Good — user runs this
Next step: run `prothon design`

# Bad — leaks implementation detail
Next step: run `/prothon-design-writer`
```

### Generated Reference Skills

The tech-researcher generates project-specific reference skills in `.agents/skills/`. These follow a simpler structure than bundled skills:

```yaml
---
name: tech-<library>
description: Reference guide for <library> — <one-line purpose>
user-invocable: false
---
```

Generated skills are reference material (not interactive agents), so they set `user-invocable: false` and contain documentation content rather than process instructions.

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
