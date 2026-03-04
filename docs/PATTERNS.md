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
| Inline content | `_UPPER_SNAKE` private constant | `_SPEC_SCAFFOLD`, `_AGENTS_CONTENT` |
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

```python
# scaffold.py — public API
def generate(dest: Path, data: dict | None = None) -> None: ...
def init_existing(cwd: Path | None = None) -> list[Path]: ...

# Private
def _template_dir() -> Path: ...
def _post_generate(dest: Path) -> None: ...
def _collect_project_details() -> dict[str, str]: ...  # init_existing Path A only
def _run_copier_init(dest: Path, data: dict[str, str]) -> None: ...
```

```python
# project.py — public API
def find_project_root(start: Path | None = None) -> Path: ...
```

```python
# git.py — public API
DiffStat = dict[str, tuple[int, int]]

def run_git(*args: str, cwd: Path | None = None) -> str: ...
def rev_parse_head(cwd: Path | None = None) -> str: ...

# Protocol + real implementation (also public)
class GitDiffProvider(Protocol): ...
class SubprocessGitDiff: ...
```

```python
# skills.py — public API
def bundled_skills_dir() -> Path: ...
def sync_skills(target: Path | None = None) -> None: ...
```

```python
# assistant.py — public API
class AssistantBackend(Protocol): ...   # 6-member contract
class ClaudeCodeBackend: ...            # Category A backend
class OpenCodeBackend: ...              # Category A backend (XDG-aware)

def register_backend(name: str, cls: type) -> None: ...
def get_backend(name: str = "claude-code") -> AssistantBackend: ...
def launch(backend: AssistantBackend, skill_name: str, cwd: Path, model: str | None = None) -> int: ...
```

```python
# versioning.py — public API
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
        output = run_git("diff", base_commit, "--name-only")
        return {line for line in output.strip().splitlines() if line.strip()}

    def diff_numstat(self, base_commit: str) -> DiffStat:
        stats: DiffStat = {}
        output = run_git("diff", base_commit, "--numstat")
        for line in output.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                added_str, removed_str, filepath = parts
                if added_str == "-" or removed_str == "-":
                    continue  # binary file
                stats[filepath] = (int(added_str), int(removed_str))
        return stats
```

### Protocol for Assistant Backends

The assistant backend contract is a protocol. Each backend is a plain class that structurally satisfies it — no inheritance required.

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


class ClaudeCodeBackend:
    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def cli_command(self) -> str:
        return "claude"

    @property
    def install_hint(self) -> str:
        return "https://docs.anthropic.com/en/docs/claude-code"

    def build_command(self, skill_name: str, cwd: Path, model: str | None = None) -> list[str]:
        # model is silently ignored — Claude Code does not support model selection via prothon
        return [self.cli_command, "--dangerously-skip-permissions", f"/{skill_name}"]

    def sync_skills(self) -> None:
        from prothon.skills import sync_skills
        sync_skills(target=Path.home() / ".claude" / "skills")

    def env_overrides(self) -> dict[str, str]:
        return {}


class OpenCodeBackend:
    @property
    def name(self) -> str:
        return "opencode"

    @property
    def cli_command(self) -> str:
        return "opencode"

    @property
    def install_hint(self) -> str:
        return "https://opencode.ai"

    def build_command(self, skill_name: str, cwd: Path, model: str | None = None) -> list[str]:
        cmd = [self.cli_command, "--prompt", f"/{skill_name}"]
        if model is not None:
            cmd.extend(["--model", model])
        return cmd

    def sync_skills(self) -> None:
        from prothon.skills import sync_skills
        raw_xdg = os.environ.get("XDG_CONFIG_HOME")
        xdg = Path(raw_xdg) if raw_xdg and Path(raw_xdg).is_absolute() else Path.home() / ".config"
        sync_skills(target=xdg / "opencode" / "skills")

    def env_overrides(self) -> dict[str, str]:
        return {}
```

### XDG_CONFIG_HOME Resolution

Backends and configuration readers that access user-level directories respect `$XDG_CONFIG_HOME` with a `~/.config` fallback. Use a one-liner pattern:

```python
raw_xdg = os.environ.get("XDG_CONFIG_HOME")
xdg = Path(raw_xdg) if raw_xdg and Path(raw_xdg).is_absolute() else Path.home() / ".config"
```

Empty or relative `XDG_CONFIG_HOME` values fall back to `~/.config` to avoid syncing into repo-relative paths. This applies to `OpenCodeBackend.sync_skills()` and `resolve_agent()` (global config lookup).

### Registry for Backend Lookup

A simple dict maps names to factory callables. Used where a user or config string selects a concrete implementation at runtime.

```python
_BACKENDS: dict[str, type[AssistantBackend]] = {
    "claude-code": ClaudeCodeBackend,
    "opencode": OpenCodeBackend,
}


def register_backend(name: str, cls: type) -> None:
    """Public extension hook for programmatic use and testing."""
    _BACKENDS[name] = cls


def get_backend(name: str = "claude-code") -> AssistantBackend:
    cls = _BACKENDS.get(name)
    if cls is None:
        registered = ", ".join(sorted(_BACKENDS.keys()))
        raise UnknownBackendError(
            f"no backend registered for '{name}' (available: {registered})"
        )
    return cls()
```

### Shared Lifecycle as Standalone Function

The shared launch lifecycle is a plain function that accepts anything satisfying `AssistantBackend`. This follows the "functions first" default — shared behavior doesn't require a base class.

```python
def launch(backend: AssistantBackend, skill_name: str, cwd: Path, model: str | None = None) -> int:
    """Shared assistant launch lifecycle."""
    if not shutil.which(backend.cli_command):
        raise AssistantNotFoundError(
            f"{backend.name} ({backend.cli_command}) not found on PATH. "
            f"Install: {backend.install_hint}"
        )
    try:
        backend.sync_skills()
    except (IOError, OSError) as exc:
        raise ProthonError(f"failed to sync skills for {backend.name}: {exc}") from exc
    env = {**os.environ, **backend.env_overrides()}
    return subprocess.run(
        backend.build_command(skill_name, cwd, model=model), cwd=cwd, env=env,
    ).returncode
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

### Guard-Clause Preconditions

Domain functions that require specific environmental conditions validate them upfront and raise domain exceptions. Guards come first, happy path follows. No nested `if/else` trees.

```python
def init_existing(cwd: Path | None = None) -> list[Path]:
    root = Path(cwd) if cwd else Path.cwd()
    if not (root / ".git").is_dir():
        raise GitError(f"not a git repository: {root}")
    if (root / "docs" / "SPEC.md").exists():
        raise ProjectAlreadyInitError(f"docs/SPEC.md already exists in {root}")
    ...
```

This keeps validation in the domain layer (not the CLI) and follows the existing "raise at source" error handling pattern.

### Inline Content Constants

Per the DESIGN key decision, doc scaffolds for `init` are inlined as module-level constants rather than read from the Copier template at runtime. This decouples `init` from Copier's file layout.

```python
_SPEC_SCAFFOLD = """\
# Project Specification

## Purpose
## Requirements
## Constraints
## Out of Scope
"""

_DESIGN_SCAFFOLD = """\
# Design Document
...
"""
```

Convention: `_UPPER_SNAKE` prefix, raw triple-quoted strings, kept together at the top of the module after imports.

### Symlink Idempotent Creation

Both `scaffold.py` and `skills.py` create symlinks. The shared pattern is: remove stale target (symlink or real dir), then create. This ensures re-running is safe.

```python
# Idempotent symlink: unlink stale, then create
if dest.is_symlink():
    dest.unlink()
elif dest.exists():
    shutil.rmtree(dest)
dest.symlink_to(source)
```

`scaffold.py` uses relative symlinks (`os.symlink("AGENTS.md", link)`) for portability within a repo. `skills.py` uses absolute symlinks (`.symlink_to(skill_dir.resolve())`) because the source is outside the project tree.

### Rich Table Rendering as Private Helpers

`cli.py` builds tables via private `_render_*` functions that return `Table` objects. Commands print them. This separates rendering logic from I/O.

```python
def _render_plan(p: Promise) -> Table:
    table = Table(title=f"PLAN: {len(p.tasks)} tasks (base: {base})")
    table.add_column("#", style="bold", width=3)
    table.add_column("Title", style="bold")
    ...
    return table

@promise_app.command("plan")
def promise_plan() -> None:
    p = promise.load_promise(promise_path)
    console.print(_render_plan(p))
```

Status styling uses a dict mapping enum values to `(label, style)` tuples — avoids branching:

```python
_status_styles = {
    CheckStatus.PASS: ("PASS", "green"),
    CheckStatus.FAIL: ("FAIL", "red"),
    CheckStatus.SKIP: ("SKIP", "yellow"),
}
for c in report.checks:
    label, style = _status_styles[c.status]
    table.add_row(c.name, Text(label, style=style), c.detail)
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

`resolve_agent(cli_value)` implements a 5-level precedence chain where the first non-empty value wins. Each level is a simple `if val: return val` guard, falling through to the next. The `cli_value` parameter receives the value from Typer (which resolves both CLI flag and env var). The function lives in `cli.py` (not `assistant.py`) because levels 3-4 read config files — these are CLI concerns, not backend concerns.

```python
def _read_toml(path: Path) -> dict:
    """Read a TOML file, returning an empty dict on parse error or missing file."""
    if not path.exists():
        return {}
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except tomlkit.exceptions.TOMLKitError:
        return {}


def _nested_get(doc: dict, *keys: str) -> str | None:
    """Walk *keys* through nested dicts, returning None if any level is not a mapping."""
    current: object = doc
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return str(current) if current is not None else None


def resolve_agent(cli_value: str | None = None) -> str:
    # Levels 1-2: CLI flag / env var (Typer resolves both into cli_value)
    if cli_value:
        return cli_value

    # Level 3: pyproject.toml [tool.prothon].agent
    try:
        root = find_project_root()
        val = _nested_get(_read_toml(root / "pyproject.toml"), "tool", "prothon", "agent")
        if val:
            return val
    except ProthonError:
        pass  # No project root — fall through

    # Level 4: global config
    raw_xdg = os.environ.get("XDG_CONFIG_HOME")
    xdg = Path(raw_xdg) if raw_xdg and Path(raw_xdg).is_absolute() else Path.home() / ".config"
    val = _nested_get(_read_toml(xdg / "prothon" / "config.toml"), "agent")
    if val:
        return val

    # Level 5: default
    return "claude-code"
```

Level 3 wraps `find_project_root()` in a `try/except ProthonError` because it's valid to run prothon outside a project (the resolution just falls through to level 4).

### Model/Provider Resolution and Join Rule

`resolve_model(cli_model, cli_provider)` implements two 5-level precedence chains (one for model, one for provider), then joins them into opencode's required `provider/model` format:

```python
def _resolve_model_value(cli_value: str | None) -> str | None:
    if cli_value:
        return cli_value
    try:
        root = find_project_root()
        val = _nested_get(_read_toml(root / "pyproject.toml"), "tool", "prothon", "model")
        if val:
            return val
    except ProthonError:
        pass
    raw_xdg = os.environ.get("XDG_CONFIG_HOME")
    xdg = Path(raw_xdg) if raw_xdg and Path(raw_xdg).is_absolute() else Path.home() / ".config"
    val = _nested_get(_read_toml(xdg / "prothon" / "config.toml"), "model")
    if val:
        return val
    return None  # defer to opencode defaults


def _resolve_provider_value(cli_value: str | None) -> str | None:
    # Same structure as _resolve_model_value, but for "provider" key
    ...


def resolve_model(cli_model: str | None, cli_provider: str | None) -> str | None:
    model = _resolve_model_value(cli_model)
    provider = _resolve_provider_value(cli_provider)

    if model is None and provider is None:
        return None  # defer to opencode defaults

    if model is not None and "/" in model:
        return model  # already in provider/model format, ignore provider flag

    if model is not None and provider is not None:
        return f"{provider}/{model}"

    raise ProthonError(
        "--provider requires --model (and vice versa). "
        "Use provider/model format or set both."
    )
```

Resolution rules:
- If `--model` already contains `/`, treat it as complete `provider/model` and ignore `--provider`
- If only one of model/provider resolves to a value (and model has no `/`), exit with error
- If neither resolves, return `None` so opencode uses its own defaults

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
        resolved_model = resolve_model(model, provider)
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

Copier is imported inside the function body, not at module level. This avoids loading Copier (and its transitive dependencies) when the module is imported for lightweight operations like `init_existing()`.

```python
def generate(dest: Path, data: dict | None = None) -> None:
    from copier import run_copy   # lazy — heavy dependency
    ...
```

This is an intentional exception to the standard import order. Use it only for genuinely heavy third-party packages where the import cost matters.

### Versioning Patterns

**Semver arithmetic** — Pure functions, no external library. Parses version string, bumps major/minor/patch, returns new string.

```python
import re

def parse_version(v: str) -> tuple[int, int, int]:
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", v)
    if not match:
        raise VersionError(f"invalid version format: {v!r}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

def bump_major(v: str) -> str:
    major, _, _ = parse_version(v)
    return f"{major + 1}.0.0"

def bump_minor(v: str) -> str:
    major, minor, _ = parse_version(v)
    return f"{major}.{minor + 1}.0"

def bump_patch(v: str) -> str:
    major, minor, patch = parse_version(v)
    return f"{major}.{minor}.{patch + 1}"
```

**File update functions** — Two functions: one for `pyproject.toml` (tomlkit preserves formatting), one for `__init__.py` (string replacement). Both accept the new version string.

```python
def update_pyproject_version(path: Path, new_version: str) -> None:
    doc = tomlkit.parse(path.read_text())
    doc["project"]["version"] = new_version
    path.write_text(tomlkit.dumps(doc))

def update_init_version(path: Path, new_version: str) -> None:
    content = path.read_text()
    updated = re.sub(
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{new_version}"',
        content,
    )
    path.write_text(updated)
```

**Git tagging** — Thin wrapper using existing `git` module. Annotated tag with message.

```python
def create_tag(version: str, cwd: Path | None = None) -> None:
    run_git("tag", "-a", f"v{version}", "-m", f"release {version}", cwd=cwd)
```

**Change detection** — Function that takes before/after SHAs and returns which bump type applies (or `None` if no relevant files changed). Used by CI workflows.

```python
def detect_bump_type(before_sha: str, after_sha: str, cwd: Path | None = None) -> str | None:
    """Returns 'major', 'minor', 'patch', or None."""
    changed = run_git("diff", "--name-only", before_sha, after_sha, cwd=cwd)
    files = {line for line in changed.strip().splitlines() if line.strip()}

    if "docs/SPEC.md" in files:
        return "major"
    if "docs/DESIGN.md" in files:
        return "minor"
    if "docs/PATTERNS.md" in files or any(f.startswith("src/") for f in files):
        return "patch"
    return None
```

### CI Workflow Patterns

**Workflow templates** — Inlined as module-level constants in `scaffold.py` (same pattern as doc scaffolds). Not separate files — keeps template/ directory focused on Copier template.

```python
_GITHUB_VERSION_BUMP_WORKFLOW = """\
name: Version Bump
on:
  push:
    branches: [main, master]
permissions:
  contents: write
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v5
      - name: Detect and bump version
        run: |
          ...
"""

_GITLAB_VERSION_BUMP_JOB = """\
version-bump:
  stage: deploy
  script:
    - ...
"""
```

**Workflow selection** — `prothon init` detects which CI platform(s) exist and writes appropriate workflows:

```python
def _detect_ci_platform(root: Path) -> list[str]:
    """Returns 'github', 'gitlab', or both."""
    platforms = []
    if (root / ".github" / "workflows").is_dir():
        platforms.append("github")
    if (root / ".gitlab-ci.yml").exists():
        platforms.append("gitlab")
    return platforms or ["github"]  # default to GitHub if none
```

If neither exists, default to GitHub (most common). User can delete unwanted file.

**pyproject.toml append** — Safe append with idempotency check:

```python
def _append_prothon_ci_section(root: Path) -> bool:
    """Append [tool.prothon.ci] if not present. Returns True if appended."""
    path = root / "pyproject.toml"
    content = path.read_text()
    if "[tool.prothon.ci]" in content:
        return False
    with path.open("a") as f:
        f.write("\n[tool.prothon.ci]\nauto_version = true\n")
    return True
```

These are internal to `init_existing()` — no new public functions in `scaffold.py`.

### Pattern Summary

| Pattern | Where | Why |
|---------|-------|-----|
| Plain functions | Default for all modules | Simplest unit, easiest to test |
| Dataclasses | Data carriers (`Promise`, `CheckResult`, `Task`) | Typed, immutable-friendly, no boilerplate |
| Protocols | All dependency injection boundaries (`GitDiffProvider`, `AssistantBackend`) | Structural typing, no inheritance, swappable for testing |
| Standalone function | Shared lifecycle (`launch()`) | Keeps protocols pure interface, follows functions-first default |
| Registry dict + `register_backend()` | Backend lookup by name | Explicit, debuggable, extensible without caller changes |
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
| CI platform detection | `_detect_ci_platform()` in `scaffold.py` | Sensible default (GitHub), user can delete unwanted |
| Idempotent config append | `_append_prothon_ci_section()` in `scaffold.py` | Safe re-runs, no duplicate sections |

## Error Handling

### Custom Exception Hierarchy

Flat hierarchy under a single base in `exceptions.py`. No deep trees.

```python
class ProthonError(Exception):
    """Base for all prothon errors. CLI catches this for clean exit."""

class ProjectNotFoundError(ProthonError):
    """No prothon project root found walking up from cwd."""

class ProjectAlreadyInitError(ProthonError):
    """docs/SPEC.md already exists — project already initialized."""

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

class VersionError(ProthonError):
    """Version string is malformed or bump operation failed."""
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

Adoption follows the same boundary pattern — `init_existing()` raises domain exceptions, `cli.py` catches and formats:

```python
# cli.py — init command
@app.command()
def init() -> None:
    """Adopt an existing project into the docs-first workflow."""
    try:
        created = init_existing()
        for path in created:
            typer.echo(f"  created {path}")
        typer.echo("\nNext step: uvx prothon spec")
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

All git interaction goes through `run_git()` which converts subprocess failures immediately. Callers never see raw `subprocess.CalledProcessError`. `GIT_TERMINAL_PROMPT=0` prevents interactive auth prompts from hanging the process. Adoption reuses this — checking "is this a git repo" via `run_git("rev-parse", "--git-dir")` naturally raises `GitError` if the directory isn't a repo.

```python
def run_git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True, text=True, cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode != 0:
        full_cmd = " ".join(["git", *args])
        raise GitError(f"{full_cmd} failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout
```

When re-raising a caught exception as a domain error but the original traceback is noise, use `from None` to suppress chaining:

```python
try:
    run_git("rev-parse", "--git-dir", cwd=root)
except GitError:
    raise GitError(f"not a git repository: {root}") from None
```

### Error Message Convention

Lowercase, specific, include the value that caused the problem.

```python
raise PromiseError(f"task index {task_index} out of range (0-{len(tasks) - 1})")
raise UnknownBackendError(f"no backend registered for '{name}' (available: {registered})")
raise VersionError(f"invalid version format: {v!r}")
```

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

```python
def test_check_task_passes_when_all_files_created(): ...
def test_check_task_fails_when_file_missing(): ...
def test_load_promise_raises_on_malformed_toml(): ...
def test_within_tolerance_boundary_values(): ...
def test_bump_major_resets_minor_and_patch(): ...
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

### Guard Clause Tests

Each precondition in a domain function gets a dedicated test. Use `tmp_path` to create the exact failing condition, assert the specific exception. One test per guard, name encodes the failing condition (`_raises_when_{condition}`).

```python
def test_init_existing_raises_when_not_git_repo(tmp_path):
    with pytest.raises(GitError, match="not a git repository"):
        init_existing(cwd=tmp_path)

def test_init_existing_raises_when_spec_exists(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# existing")
    with pytest.raises(ProjectAlreadyInitError):
        init_existing(cwd=tmp_path)
```

### Filesystem Assertion Helpers

Adoption creates files, directories, and symlinks. Use simple helpers in `conftest.py` to keep happy-path tests readable:

```python
# conftest.py
def assert_symlink_to(link: Path, target_name: str) -> None:
    """Assert that link is a symlink pointing to target_name."""
    assert link.is_symlink(), f"{link} is not a symlink"
    assert os.readlink(link) == target_name, (
        f"{link} points to {os.readlink(link)}, expected {target_name}"
    )

# test_scaffold.py
def test_init_existing_creates_all_artifacts(tmp_path):
    run_git("init", cwd=tmp_path)
    created = init_existing(cwd=tmp_path)

    assert (tmp_path / "docs" / "SPEC.md").exists()
    assert (tmp_path / "docs" / "DESIGN.md").exists()
    assert (tmp_path / "docs" / "PATTERNS.md").exists()
    assert (tmp_path / ".agents" / "skills").is_dir()
    assert_symlink_to(tmp_path / "CLAUDE.md", "AGENTS.md")
    assert_symlink_to(tmp_path / "GEMINI.md", "AGENTS.md")
    assert_symlink_to(tmp_path / "AGENT.md", "AGENTS.md")
```

### Idempotency and Non-Destructiveness Tests

Since R17 requires `init` must not modify existing files, test that pre-existing content survives:

```python
def test_init_existing_does_not_modify_existing_files(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    init_existing(cwd=tmp_path)
    assert "[tool.ruff]" in (tmp_path / "pyproject.toml").read_text()
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

### Versioning Tests

**Unit tests for semver arithmetic** — Direct function tests, no filesystem:

```python
# test_versioning.py

def test_parse_version_extracts_components():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v2.0.0") == (2, 0, 0)

def test_parse_version_rejects_invalid():
    with pytest.raises(VersionError, match="invalid version"):
        parse_version("not-a-version")

def test_bump_major_resets_minor_and_patch():
    assert bump_major("1.2.3") == "2.0.0"

def test_bump_minor_resets_patch():
    assert bump_minor("1.2.3") == "1.3.0"

def test_bump_patch_increments_patch():
    assert bump_patch("1.2.3") == "1.2.4"
```

**File update tests** — Use `tmp_path`:

```python
def test_update_pyproject_preserves_comments(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n# comment\n')
    update_pyproject_version(pyproject, "0.2.0")
    content = pyproject.read_text()
    assert 'version = "0.2.0"' in content
    assert "# comment" in content

def test_update_init_version(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "0.1.0"\n')
    update_init_version(init, "0.2.0")
    assert '__version__ = "0.2.0"' in init.read_text()
```

**Change detection tests** — Use `run_git` with temp repo:

```python
def test_detect_bump_type_returns_major_for_spec_change(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# spec")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "docs" / "SPEC.md").write_text("# updated")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "spec change", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "major"

def test_detect_bump_type_returns_none_for_readme_only(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# readme")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "README.md").write_text("# updated")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "readme update", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) is None
```

### What Not to Test

- Third-party library behavior (Typer routing, tomlkit parsing)
- Trivial dataclass construction
- Private helpers — unless they contain non-obvious logic (like `_within_tolerance`)
