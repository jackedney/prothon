# Design Document

## Architecture

### Module Structure

Flat module layout with all domain modules at one level under `src/prothon/`. CLI definitions live in `cli.py` alongside domain modules — no separate CLI subpackage.

```
src/prothon/
    __init__.py
    cli.py              # Typer app, command definitions, output formatting
    scaffold.py         # Template rendering, copier answers, git init, project adoption
    skills.py           # Skill discovery, symlink management
    promise.py          # Promise data model, TOML I/O, git diff verification
    project.py          # Project root detection, shared project context
    git.py              # Thin typed wrapper around git CLI via subprocess
    assistant.py        # Abstract assistant interface and backend registry
    exceptions.py       # Custom exception hierarchy
    skills/             # Bundled skill assets (non-Python, 7 directories)

template/               # Bundled Copier project template (Jinja2), at project root
```

This layout is driven by the number of subsystems in the SPEC (scaffolding, doc agents, execution, compliance, promise system, skill management — requirements 1, 22, 25, 32, 26, 42) each mapping to one module. At the expected scale of 2-5 KLOC, flat is navigable without namespace overhead.

### Module Dependencies

```
cli.py
  ├── scaffold.generate(), init_existing()
  ├── assistant.get_backend(), launch()
  └── promise.load_promise(), plan(), check_task(), status(), complete_task(), cleanup()

assistant.py
  └── skills.sync_skills(target)

cli.py (assistant resolution)
  ├── typer Option + envvar for --assistant / PROTHON_ASSISTANT
  ├── project.find_project_root() → pyproject.toml [tool.prothon].assistant
  └── ~/.config/prothon/config.toml → assistant

All modules
  ├── project.find_project_root()
  ├── git.*
  └── exceptions.*
```

`cli.py` is the only module that depends on Typer for command definitions. Domain modules (`scaffold.py`, `promise.py`, etc.) are plain Python and independently testable without invoking the CLI framework. This separation serves requirement 40 (all workflows invocable via CLI) while keeping domain logic framework-independent.

### Bundled Assets

Two non-Python asset directories are bundled with the project:

- `skills/` — 7 bundled skill directories inside the package, each containing a `SKILL.md`. Discovered at runtime via `Path(__file__).parent / "skills"`. Serves requirements 42 (skills bundled with package) and 22 (dedicated interactive agents).
- `template/` — Copier project template at the repository root (not inside the package), with `copier.yml`, Jinja2-templated files, and post-generation tasks. Serves requirements 1-9 (project scaffolding).

`skills/` is included automatically as part of the `src/prothon` package. `template/` is included via `[tool.hatch.build.targets.wheel.force-include]` since it lives outside the package root.

### Assistant Abstraction

Each assistant backend encapsulates its binary name, invocation flags, skill sync target, environment overrides, and command construction. A shared launch lifecycle handles: binary detection, skill syncing, environment merging, subprocess execution, and return code checking.

AI coding CLIs fall into two structural categories based on how they receive skill instructions:

- **Category A (native skill directories)** — Claude Code and opencode have filesystem-based skill discovery. Prothon symlinks bundled skills into their discovery directory and invokes them by name via slash commands.
- **Category B (prompt injection)** — Tools like Codex CLI, Gemini CLI, Goose, and Aider have no native skill directory. Skill content must be injected into the prompt or written to a backend-specific instruction file. These are out of scope per the SPEC but the abstraction accommodates them for future expansion.

A registry maps assistant names to backend classes. Claude Code and opencode are registered. Adding a new assistant requires one backend implementation (~15-25 lines) and one registry entry. No caller changes needed. A `register_backend()` function provides a public extension hook for programmatic use and testing. Entry points are deferred until third-party demand materialises. This serves requirements 41-42 (Claude Code and opencode support, assistant selection).

### Promise Verification

The promise system uses typed dataclass models (`Task`, `Metadata`, `Promise`) to represent the change contract declared in `docs/change_promise.toml`. Verification logic lives in a standalone `check_task()` function that accepts a `GitDiffProvider` protocol, enabling subprocess-free testing with a fake implementation.

Verification checks file existence (for creates/removes), git diff analysis (for modifications), and line count tolerance (+-30% or +-30 lines, whichever is greater). Per-file `FileCheckDetail` results provide structured error data for programmatic consumers. This serves requirements 25-31 (execution verification) and 32-35 (compliance verification).

## Technology Choices

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint-driven parameter inference | R40: CLI-invocable workflows | click, argparse |
| copier (>=9.0) | Project templating with native `copier update` support | R1-R9: project scaffolding | cookiecutter, custom Jinja2 |
| tomlkit (>=0.13,<1.0) | TOML read/write with comment and formatting preservation | R25-R26: change promise contract | tomllib+tomli-w, toml |
| rich (via typer) | Table rendering for promise plans, status, and compliance reports | R33: compliance report with PASS/FAIL/SKIP status | tabulate, click echo/style |
| subprocess (stdlib) | Git CLI interaction via thin typed wrapper | R7: git init, R29: promise verification | GitPython, pygit2, dulwich |

### Rationale

**Typer** — Already in use. Lowest boilerplate for 12 commands across two nesting levels. Type hints drive parameter inference. Rich-formatted help output included. Actively maintained (v0.24.1, Feb 2026). If ever abandoned, migration to raw Click is mechanical since Typer generates Click objects internally.

**Copier** — Template updating via `copier update` with 3-way merge is central to prothon's value proposition. When prothon's template evolves, existing projects pull in changes without losing local modifications. Clean Python API (`run_copy`, `run_update`, `run_recopy`) designed for library embedding. Declarative prompts with types, validation, and conditions. Neither cookiecutter nor custom Jinja2 provides template updating.

**tomlkit** — `change_promise.toml` is a human-authored contract. When prothon programmatically updates fields like `completed` or `attempts`, it must not destroy comments, spacing, or ordering. Only tomlkit preserves these on roundtrip. Rich document construction helpers (`comment()`, `table()`, `aot()`) enable scaffolding well-formatted TOML from scratch. Maintained by the Poetry organization. The 18x parsing slowdown vs tomllib is irrelevant for small config files.

**Rich** — Already installed at zero marginal cost (Typer unconditionally depends on it). Best-in-class table rendering with per-cell styling, colored PASS/FAIL, and column alignment. Using it for promise plans, status, and compliance reports is free. Interactive prompts remain on `typer.prompt()`.

**subprocess for git** — Every git operation prothon needs maps to a single CLI command with a machine-readable output flag (`--numstat`, `--name-only`, `--porcelain`). No operation benefits from in-process git access. Zero dependencies. `--numstat` (critical for promise verification) is trivial via subprocess but problematic with dulwich. List-form arguments with `GIT_TERMINAL_PROMPT=0` provide a minimal attack surface.

## Interfaces

### CLI Commands

All commands that launch an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`) respect the global `--assistant` / `-a` option and the `PROTHON_ASSISTANT` environment variable. See the Assistant Configuration Contract below for the full resolution chain.

| Command | Input | Output | Subsystem |
|---------|-------|--------|-----------|
| `prothon new` | Interactive prompts: module name, description, author name, email, Python version, license | Scaffolded project directory with git repo | scaffold.py |
| `prothon init` | None (validates cwd) | `docs/` scaffolds, `AGENTS.md`, agent symlinks, `.agents/skills/` | scaffold.py |
| `prothon spec` | None (launches interactive session) | Populated `docs/SPEC.md` | cli.py → assistant.py (skill subprocess) |
| `prothon design` | None (launches interactive session) | Populated `docs/DESIGN.md` + generated reference skills | cli.py → assistant.py (skill subprocess) |
| `prothon patterns` | None (launches interactive session) | Populated `docs/PATTERNS.md` | cli.py → assistant.py (skill subprocess) |
| `prothon execute` | None (reads docs, plans, launches subagents) | Implemented code, committed per-task | cli.py → assistant.py (skill subprocess) |
| `prothon compliance` | None (reads docs and code) | Compliance report table (PASS/FAIL per requirement) | cli.py → assistant.py (skill subprocess) |
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

Every assistant backend must satisfy the `AssistantBackend` protocol (structural typing, no inheritance required):

- `name` — human-readable name for error messages (e.g. "Claude Code", "opencode")
- `cli_command` — binary name to look up on PATH (e.g. "claude", "opencode")
- `install_hint` — installation URL or command for actionable error messages when the binary is missing
- `build_command(skill_name, cwd)` — constructs the subprocess argv for launching a session. Category A backends reference the skill by name (e.g. `["claude", "--dangerously-skip-permissions", "/prothon-spec-writer"]`). Category B backends read skill content and inject it into the prompt argument.
- `sync_skills()` — installs/symlinks bundled skills to the assistant's discovery location. Category A backends call `skills.sync_skills(target=...)` with their specific directory. Category B backends may be a no-op.
- `env_overrides()` — returns a dict of extra environment variables needed for non-interactive execution (e.g. `{"GOOSE_MODE": "auto"}`). Returns an empty dict if none are needed.

Registered backends:

| Key | Backend | Binary | Skill sync target | Category |
|-----|---------|--------|-------------------|----------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` | A (native skills) |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) | A (native skills) |

A shared launch lifecycle handles: binary existence check (via `shutil.which()`), skill syncing, environment merging (`os.environ` + `env_overrides()`), subprocess execution, and return code reporting. When the binary is missing, the error message includes the backend's `install_hint`.

A `register_backend(name, cls)` function allows programmatic extension for testing or embedding. Entry points are not used — there are no third-party consumers, and adding entry point discovery later is a trivial change.

### Assistant Configuration Contract

The user selects their preferred assistant via a 5-level precedence chain. The first non-empty value wins:

| Priority | Source | Mechanism | Example |
|----------|--------|-----------|---------|
| 1 (highest) | CLI flag | `--assistant` / `-a` global option on Typer app callback | `prothon --assistant opencode spec` |
| 2 | Environment variable | `PROTHON_ASSISTANT` | `export PROTHON_ASSISTANT=opencode` |
| 3 | Project config | `[tool.prothon]` in `pyproject.toml` | `assistant = "opencode"` |
| 4 | Global config | `~/.config/prothon/config.toml` (respects `$XDG_CONFIG_HOME`) | `assistant = "opencode"` |
| 5 (lowest) | Default | Hardcoded | `"claude-code"` |

Resolution is implemented as a `resolve_assistant()` function in `cli.py` (~20 lines). Typer natively handles levels 1-2 via the `envvar=` parameter on `typer.Option()`. Levels 3-4 are resolved by reading TOML files with `tomlkit` (already a dependency).

The `--assistant` option is global (on the app callback), not per-command, matching the pattern used by `ruff --config` and `uv --config-file`. It applies to all commands that launch an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`). Commands that don't launch a session (`new`, `init`, `promise *`) ignore it.

Valid backend keys match the registry: `claude-code`, `opencode`. When an invalid key is provided, the error message lists all registered backends. When the resolved backend's binary is missing, the error message includes the backend's `install_hint`.

Config file format examples:

```toml
# pyproject.toml
[tool.prothon]
assistant = "opencode"
```

```toml
# ~/.config/prothon/config.toml
assistant = "opencode"
```

### Compliance Report Contract

The compliance checker reads all three documentation levels and all source code, then produces three tables (SPEC compliance, DESIGN compliance, PATTERNS compliance). Each row contains: the checkable statement, a PASS/FAIL/SKIP status, and `file:line` evidence. SKIP indicates a check was not applicable (e.g., no files declared for that category). A summary section reports overall percentage and prioritized action items.

### Adoption Contract

`prothon init` overlays the documentation-driven workflow onto an existing Python project without touching its code, configuration, or git history. It performs the following steps in order:

1. Verifies the current directory is a git repository (exits with error if not).
2. Verifies `docs/SPEC.md` does not exist (exits with error if it does, directing the user to `prothon new` or manual setup).
3. Creates `docs/` directory with empty scaffolds: `SPEC.md`, `DESIGN.md`, `PATTERNS.md` — each containing only markdown section headers, inlined in `scaffold.py`.
4. Creates `AGENTS.md` at the project root with agent instruction content (inlined in `scaffold.py`), plus symlinks: `CLAUDE.md → AGENTS.md`, `GEMINI.md → AGENTS.md`, `AGENT.md → AGENTS.md`.
5. Creates `.agents/skills/` directory for project-specific reference skills.
6. Prints a summary of all created files and suggests `prothon spec` as the next step.

The command must not modify existing files, `pyproject.toml`, dependencies, toolchain configuration, pre-commit hooks, CI workflows, or git history.

### Scaffolding Contract

`prothon new` collects six inputs (module name, description, author name, author email, Python version, license) and passes them to Copier's `run_copy()`. The template produces a complete project with: `src/` layout, `pyproject.toml`, pre-commit hooks, CI workflows, git repo with initial commit, agent instruction files, doc scaffolds, and `.agents/skills/` directory. A `.copier-answers.yml` file is written to enable future `copier update` calls.

### Skill Discovery Contract

Bundled skills live in `src/prothon/skills/` as directories containing `SKILL.md`. On every CLI invocation that launches an assistant session, the active backend's `sync_skills()` method symlinks each bundled skill directory into that backend's discovery location. The `skills.sync_skills(target)` function accepts a `target` parameter — each backend passes its own directory:

| Backend | Skill sync target |
|---------|-------------------|
| Claude Code | `~/.claude/skills/` |
| opencode | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) |

Symlinks point directly from the backend's skill directory to the bundled package directory. Each backend maintains its own set of symlinks (no shared central location). The duplication cost is zero since symlinks have no disk footprint.

Project-specific reference skills generated by the tech-researcher live in each project's `.agents/skills/` directory. Both Claude Code and opencode discover `.agents/skills/` natively, so no backend-specific handling is needed for project skills.

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
| Init scaffold sourcing | Inline markdown headers in `scaffold.py` | Read from Copier template at runtime | Scaffolds are 3-5 lines each. Inlining avoids coupling init to Copier's internal file layout. Template restructuring cannot break init. |
| Skill sync strategy | Per-backend direct symlinks with parameterised `sync_skills(target)` | Central location with backend pointers; single shared directory | Per-backend symlinks avoid symlink-chain resolution issues across different tools. Duplication cost is zero (symlinks only). Simpler two-backend setup. Central location can be revisited if backend count exceeds 4. |
| Assistant selection | 5-level precedence: CLI flag > env var > pyproject.toml > global config > default | Per-command flag; env var only; config file only | Matches universal Python ecosystem convention (uv, ruff, pip, pytest). Typer handles levels 1-2 natively. No new dependencies — tomlkit reads both config sources. |
| Backend registry | Internal dict with `register_backend()` hook | Entry points (`importlib.metadata`); plugin framework (stevedore, pluggy) | Zero third-party consumers exist. Internal dict is zero-overhead, grep-discoverable, and type-safe. Entry point discovery adds import-time cost and failure modes. Migration to entry points later is a 10-line change. |
| Backend protocol scope | 6 members: name, cli_command, install_hint, build_command, sync_skills, env_overrides | Minimal 4 members (current); maximal with interactive/non-interactive mode flag | install_hint enables actionable error messages. env_overrides cleanly separates env var concerns from command construction. Interactive/non-interactive mode flag deferred until execute workflow needs it. |
