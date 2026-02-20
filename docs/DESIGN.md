# Design Document

## Architecture

### Module Structure

Flat module layout with all domain modules at one level under `src/prothon/`. CLI definitions live in `cli.py` alongside domain modules — no separate CLI subpackage.

```
src/prothon/
    __init__.py
    cli.py              # Typer app, command definitions, output formatting
    scaffold.py         # Template rendering, copier answers, git init
    skills.py           # Skill discovery, symlink management
    promise.py          # Promise data model, TOML I/O, git diff verification
    project.py          # Project root detection, shared project context
    git.py              # Thin typed wrapper around git CLI via subprocess
    assistant.py        # Abstract assistant interface and backend registry
    exceptions.py       # Custom exception hierarchy
    skills/             # Bundled skill assets (non-Python, 7 directories)
    template/           # Bundled Copier project template (Jinja2)
```

This layout is driven by the number of subsystems in the SPEC (scaffolding, doc agents, execution, compliance, promise system, skill management — requirements 1, 14, 17, 24, 32, 34) each mapping to one module. At the expected scale of 2-5 KLOC, flat is navigable without namespace overhead.

### Module Dependencies

```
cli.py
  ├── scaffold.generate()
  ├── assistant.get_backend(), launch()
  └── promise.load_promise(), plan(), check_task(), status(), complete_task(), cleanup()

assistant.py
  └── skills.sync_skills()

All modules
  ├── project.find_project_root()
  ├── git.*
  └── exceptions.*
```

`cli.py` is the only module that depends on Typer for command definitions. Domain modules (`scaffold.py`, `promise.py`, etc.) are plain Python and independently testable without invoking the CLI framework. This separation serves requirement 32 (all workflows invocable via CLI) while keeping domain logic framework-independent.

### Bundled Assets

Two non-Python asset directories live inside the package:

- `skills/` — 7 bundled skill directories, each containing a `SKILL.md`. Discovered at runtime via `Path(__file__).parent / "skills"`. Serves requirements 34 (skills bundled with package) and 14 (dedicated interactive agents).
- `template/` — Copier project template with `copier.yml`, Jinja2-templated files, and post-generation tasks. Serves requirements 1-9 (project scaffolding).

`skills/` is included automatically as part of the `src/prothon` package. `template/` is included via `[tool.hatch.build.targets.wheel.force-include]` since it lives outside the package root.

### Assistant Abstraction

Each assistant backend encapsulates its binary name, invocation flags, skill sync target, and command construction. A shared launch lifecycle handles: binary detection, skill syncing, subprocess execution, and return code checking.

A registry maps assistant names to backends. Currently only Claude Code is registered. Adding a new assistant requires one backend implementation (~20 lines) and one registry entry. No caller changes needed. This serves requirement 33 (Claude Code support) while preparing for the planned future expansion to other assistants.

### Promise Verification

The promise system uses typed dataclass models (`Task`, `Metadata`, `Promise`) to represent the change contract declared in `docs/change_promise.toml`. Verification logic lives in a standalone `check_task()` function that accepts a `GitDiffProvider` protocol, enabling subprocess-free testing with a fake implementation.

Verification checks file existence (for creates/removes), git diff analysis (for modifications), and line count tolerance (+-30% or +-30 lines, whichever is greater). Per-file `FileCheckDetail` results provide structured error data for programmatic consumers. This serves requirements 17-23 (execution verification) and 24-27 (compliance verification).

## Technology Choices

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint-driven parameter inference | R32: CLI-invocable workflows | click, argparse |
| copier (>=9.0) | Project templating with native `copier update` support | R1-R9: project scaffolding | cookiecutter, custom Jinja2 |
| tomlkit (>=0.13,<1.0) | TOML read/write with comment and formatting preservation | R17-R18: change promise contract | tomllib+tomli-w, toml |
| rich (via typer) | Table rendering for promise plans, status, and compliance reports | R25: compliance report with PASS/FAIL status | tabulate, click echo/style |
| subprocess (stdlib) | Git CLI interaction via thin typed wrapper | R7: git init, R21: promise verification | GitPython, pygit2, dulwich |

### Rationale

**Typer** — Already in use. Lowest boilerplate for 11 commands across two nesting levels. Type hints drive parameter inference. Rich-formatted help output included. Actively maintained (v0.24.0, Feb 2026). If ever abandoned, migration to raw Click is mechanical since Typer generates Click objects internally.

**Copier** — Template updating via `copier update` with 3-way merge is central to prothon's value proposition. When prothon's template evolves, existing projects pull in changes without losing local modifications. Clean Python API (`run_copy`, `run_update`, `run_recopy`) designed for library embedding. Declarative prompts with types, validation, and conditions. Neither cookiecutter nor custom Jinja2 provides template updating.

**tomlkit** — `change_promise.toml` is a human-authored contract. When prothon programmatically updates fields like `completed` or `attempts`, it must not destroy comments, spacing, or ordering. Only tomlkit preserves these on roundtrip. Rich document construction helpers (`comment()`, `table()`, `aot()`) enable scaffolding well-formatted TOML from scratch. Maintained by the Poetry organization. The 18x parsing slowdown vs tomllib is irrelevant for small config files.

**Rich** — Already installed at zero marginal cost (Typer unconditionally depends on it). Best-in-class table rendering with per-cell styling, colored PASS/FAIL, and column alignment. Using it for promise plans, status, and compliance reports is free. Interactive prompts remain on `typer.prompt()`.

**subprocess for git** — Every git operation prothon needs maps to a single CLI command with a machine-readable output flag (`--numstat`, `--name-only`, `--porcelain`). No operation benefits from in-process git access. Zero dependencies. `--numstat` (critical for promise verification) is trivial via subprocess but problematic with dulwich. List-form arguments with `GIT_TERMINAL_PROMPT=0` provide a minimal attack surface.

## Interfaces

### CLI Commands

| Command | Input | Output | Subsystem |
|---------|-------|--------|-----------|
| `prothon new` | Interactive prompts: module name, description, author name, email, Python version, license | Scaffolded project directory with git repo | scaffold.py |
| `prothon spec` | None (launches interactive session) | Populated `docs/SPEC.md` | agents.py |
| `prothon design` | None (launches interactive session) | Populated `docs/DESIGN.md` + generated reference skills | agents.py |
| `prothon patterns` | None (launches interactive session) | Populated `docs/PATTERNS.md` | agents.py |
| `prothon execute` | None (reads docs, plans, launches subagents) | Implemented code, committed per-task | execute.py |
| `prothon compliance` | None (reads docs and code) | Compliance report table (PASS/FAIL per requirement) | compliance.py |
| `prothon promise plan` | None (reads `change_promise.toml`) | Pretty-printed task table | promise.py |
| `prothon promise status` | None (reads `change_promise.toml`) | Task completion progress table | promise.py |
| `prothon promise check N` | Task index | Verification report (per-file PASS/FAIL) | promise.py |
| `prothon promise complete N` | Task index, attempt count | Updated `change_promise.toml` | promise.py |
| `prothon promise cleanup` | None | Removes `change_promise.toml` | promise.py |

### Promise Contract Format

`docs/change_promise.toml` — the contract between the planning phase and execution phase of `prothon execute`.

```
[metadata]
base_commit = "<SHA at plan time>"
created_at = "<ISO 8601>"

[[tasks]]
title = "<task identifier>"
goal = "<what this task accomplishes>"
success_criteria = "<how to verify completion>"
files_to_create = ["<path>", ...]
files_to_modify = ["<path>", ...]
files_to_remove = ["<path>", ...]
expected_lines_added = <int>
expected_lines_removed = <int>
context_files = ["<path>", ...]
doc_sections = ["<doc>:<section>", ...]
reference_skills = ["<skill-name>", ...]
dependencies = [<task-index>, ...]
completed = <bool>
attempts = <int>
```

### Promise Verification Contract

Each task verification produces a `TaskCheckReport` containing a list of `CheckResult` entries. Each `CheckResult` has a `CheckStatus` enum (PASS/FAIL/SKIP), a summary string, and a list of `FileCheckDetail` records providing per-file granularity (path, expected state, actual state, status). SKIP indicates a check was not applicable (e.g. no files declared for that category). A report passes if it contains no FAIL entries — SKIP results do not affect the outcome.

Tolerance for line counts: +-30% or +-30 lines, whichever is greater. Binary files are excluded from line counts.

### Assistant Backend Contract

Every assistant backend must provide:

- `name` — human-readable name for error messages
- `cli_command` — binary name to look up on PATH
- `build_command(skill_name)` — constructs the subprocess argv for launching a session
- `sync_skills()` — installs/symlinks bundled skills to the assistant's discovery location

A shared launch lifecycle handles: binary existence check, skill syncing, subprocess execution, and return code reporting.

### Compliance Report Contract

The compliance checker reads all three documentation levels and all source code, then produces three tables (SPEC compliance, DESIGN compliance, PATTERNS compliance). Each row contains: the checkable statement, a PASS/FAIL status, and `file:line` evidence. A summary section reports overall percentage and prioritized action items.

### Scaffolding Contract

`prothon new` collects six inputs (module name, description, author name, author email, Python version, license) and passes them to Copier's `run_copy()`. The template produces a complete project with: `src/` layout, `pyproject.toml`, pre-commit hooks, CI workflows, git repo with initial commit, agent instruction files, doc scaffolds, and `.agents/skills/` directory. A `.copier-answers.yml` file is written to enable future `copier update` calls.

### Skill Discovery Contract

Bundled skills live in `src/prothon/skills/` as directories containing `SKILL.md`. On every CLI invocation, `sync_skills()` symlinks each skill directory into the active assistant's skill discovery location (e.g., `~/.claude/skills/` for Claude Code). Project-specific reference skills generated by the tech-researcher live in each project's `.agents/skills/` directory.

## Key Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Module structure | Flat modules, one per subsystem | Nested packages by subsystem; hybrid flat core + CLI package | 6 subsystems map cleanly to 6 flat modules at 2-5 KLOC. Minimal refactor. Any module can be promoted to a subpackage later without changing caller imports. |
| CLI framework | Typer | Click, argparse | Already in use and working. Lowest boilerplate. Type-hint inference. Switching would be a rewrite with zero functional benefit. |
| Templating engine | Copier | Cookiecutter, custom Jinja2 | Template updating (`copier update` with 3-way merge) is the decisive factor. Neither alternative provides it. Clean Python API for library embedding. |
| TOML library | tomlkit | tomllib + tomli-w, toml (uiri) | Comment/formatting preservation on roundtrip is essential for human-authored promise files. Single library for read and write. Maintained by Poetry organization. |
| Git interaction | subprocess wrapper | GitPython, pygit2, dulwich | All operations are single CLI commands with machine-readable flags. `--numstat` is trivial via subprocess but problematic with dulwich. Zero dependencies. GitPython is in maintenance mode with multiple CVEs. |
| Terminal output | Rich (via Typer dependency) | tabulate + print, Click echo/style | Already installed at zero marginal cost. Best-in-class tables. Adding tabulate would be a new dependency for worse output. |
| Assistant invocation | Pluggable backends with shared launch lifecycle | Direct subprocess per-assistant, configuration-driven templates | Variation between assistants is structural (different CLIs, skill mechanisms, permissions), not parametric. A shared contract keeps callers backend-agnostic. Config templates break when assistants differ structurally. |
| Promise verification | Typed dataclass models with `GitDiffProvider` protocol | Plain dict + subprocess, state machine | Protocol injection eliminates fragile mock patching in tests. Per-file `FileCheckDetail` enables structured error reporting. State machine overlaps with the execute skill's orchestrator. |
