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
    versioning.py       # Semantic version detection, bumping, git tagging
    project.py          # Project root detection, shared project context
    git.py              # Thin typed wrapper around git CLI via subprocess
    assistant.py        # Abstract assistant interface and backend registry
    exceptions.py       # Custom exception hierarchy
    skills/             # Bundled skill assets (non-Python, 7 directories)

template/               # Bundled Copier project template (Jinja2), at project root
```

This layout is driven by the number of subsystems in the SPEC (scaffolding, doc agents, execution, compliance, promise system, versioning, skill management — requirements 1-9, 22, 25-26, 32-35, 40-48, 52) each mapping to one module. At the expected scale of 2-5 KLOC, flat is navigable without namespace overhead.

### Module Dependencies

```
cli.py
  ├── scaffold.generate(), init_existing()
  ├── assistant.get_backend(), launch()
  └── promise.load_promise(), plan(), check_task(), status(), complete_task(), cleanup()

assistant.py
  └── skills.sync_skills(target)

versioning.py
  ├── git.* (for tag operations)
  └── tomlkit (for version file updates)

cli.py (agent resolution — per-command --agent option)
  ├── typer Option + envvar for --agent / PROTHON_AGENT (on each session command)
  ├── project.find_project_root() → pyproject.toml [tool.prothon].agent
  └── ~/.config/prothon/config.toml → agent

All modules
  ├── project.find_project_root()
  ├── git.*
  └── exceptions.*
```

`cli.py` is the only module that depends on Typer for command definitions. Domain modules (`scaffold.py`, `promise.py`, `versioning.py`, etc.) are plain Python and independently testable without invoking the CLI framework. This separation serves requirement 49 (all workflows invocable via CLI) while keeping domain logic framework-independent.

### Bundled Assets

Two non-Python asset directories are bundled with the project:

- `skills/` — 7 bundled skill directories inside the package, each containing a `SKILL.md`. Discovered at runtime via `Path(__file__).parent / "skills"`. Serves requirements 52 (skills bundled with package) and 22 (dedicated interactive agents).
- `template/` — Copier project template at the repository root (not inside the package), with `copier.yml`, Jinja2-templated files, and post-generation tasks. Serves requirements 1-9 (project scaffolding).

`skills/` is included automatically as part of the `src/prothon` package. `template/` is included via `[tool.hatch.build.targets.wheel.force-include]` since it lives outside the package root.

### Assistant Abstraction

Each assistant backend encapsulates its binary name, invocation flags, skill sync target, environment overrides, and command construction. A shared launch lifecycle handles: binary detection, skill syncing, environment merging, subprocess execution, and return code checking.

AI coding CLIs fall into two structural categories based on how they receive skill instructions:

- **Category A (native skill directories)** — Claude Code and opencode have filesystem-based skill discovery. Prothon symlinks bundled skills into their discovery directory and invokes them by name via slash commands.
- **Category B (prompt injection)** — Tools like Codex CLI, Gemini CLI, Goose, and Aider have no native skill directory. Skill content must be injected into the prompt or written to a backend-specific instruction file. These are out of scope per the SPEC but the abstraction accommodates them for future expansion.

A registry maps assistant names to backend classes. Claude Code and opencode are registered. Adding a new assistant requires one backend implementation (~15-25 lines) and one registry entry. No caller changes needed. A `register_backend()` function provides a public extension hook for programmatic use and testing. Entry points are deferred until third-party demand materialises. This serves requirements 50-51 (Claude Code and opencode support, assistant selection).

### Promise Verification

The promise system uses typed dataclass models (`Task`, `Metadata`, `Promise`) to represent the change contract declared in `docs/change_promise.toml`. Verification logic lives in a standalone `check_task()` function that accepts a `GitDiffProvider` protocol, enabling subprocess-free testing with a fake implementation.

Verification checks file existence (for creates/removes), git diff analysis (for modifications), and line count tolerance (+-30% or +-30 lines, whichever is greater). Per-file `FileCheckDetail` results provide structured error data for programmatic consumers. This serves requirements 25-31 (execution verification) and 32-35 (compliance verification).

## Technology Choices

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint-driven parameter inference | R49: CLI-invocable workflows | click, argparse |
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

All commands that launch an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`) accept a per-command `--agent` / `-a` option and the `PROTHON_AGENT` environment variable. When the resolved agent is `opencode`, `--model` / `-m` and `--provider` / `-p` options control which model is used. See the Agent Configuration Contract and Model Configuration Contract below for the full resolution chains.

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

Each task verification produces a `TaskCheckReport` containing a list of `CheckResult` entries. Each `CheckResult` has a `CheckStatus` enum (members: `PASSED`, `FAILED`, `SKIPPED` with values `"PASS"`, `"FAIL"`, `"SKIP"`), a summary string, and a list of `FileCheckDetail` records providing per-file granularity (path, expected state, actual state, status). SKIPPED indicates a check was not applicable (e.g. no files declared for that category). A report passes if it contains no FAILED entries — SKIPPED results do not affect the outcome.

Tolerance for line counts: +-30% or +-30 lines, whichever is greater. Binary files are excluded from line counts.

### Assistant Backend Contract

Every assistant backend must satisfy the `AssistantBackend` protocol (structural typing, no inheritance required):

- `name` — human-readable name for error messages (e.g. "Claude Code", "opencode")
- `cli_command` — binary name to look up on PATH (e.g. "claude", "opencode")
- `install_hint` — installation URL or command for actionable error messages when the binary is missing
- `build_command(skill_name, cwd, model=None)` — constructs the subprocess argv for launching a session. The optional `model` parameter is the resolved `provider/model` string (see Model Configuration Contract). Category A backends reference the skill by name via slash commands. Claude Code uses `["claude", "--dangerously-skip-permissions", "/prothon-spec-writer"]`; opencode uses `["opencode", "--prompt", "/prothon-spec-writer"]` with the `--prompt` flag. When `model` is provided, backends that support it append `["--model", model]` to the argv. Category B backends read skill content and inject it into the prompt argument.
- `sync_skills()` — installs/symlinks bundled skills to the assistant's discovery location. Category A backends call `skills.sync_skills(target=...)` with their specific directory. Category B backends may be a no-op.
- `env_overrides()` — returns a dict of extra environment variables needed for non-interactive execution (e.g. `{"GOOSE_MODE": "auto"}`). Returns an empty dict if none are needed.

Registered backends:

| Key | Backend | Binary | Skill sync target | Category |
|-----|---------|--------|-------------------|----------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` | A (native skills) |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) | A (native skills) |

A shared launch lifecycle handles: binary existence check (via `shutil.which()`), skill syncing, environment merging (`os.environ` + `env_overrides()`), subprocess execution, and return code reporting. When the binary is missing, the error message includes the backend's `install_hint`.

A `register_backend(name, cls)` function allows programmatic extension for testing or embedding. Entry points are not used — there are no third-party consumers, and adding entry point discovery later is a trivial change.

### Agent Configuration Contract

The user selects their preferred agent via a 5-level precedence chain. The first non-empty value wins:

| Priority | Source | Mechanism | Example |
|----------|--------|-----------|---------|
| 1 (highest) | CLI flag | `--agent` / `-a` per-command option | `prothon spec --agent opencode` |
| 2 | Environment variable | `PROTHON_AGENT` | `export PROTHON_AGENT=opencode` |
| 3 | Project config | `[tool.prothon]` in `pyproject.toml` | `agent = "opencode"` |
| 4 | Global config | `~/.config/prothon/config.toml` (respects `$XDG_CONFIG_HOME`) | `agent = "opencode"` |
| 5 (lowest) | Default | Hardcoded | `"claude-code"` |

Resolution is implemented as a `resolve_agent(cli_value)` function in `cli.py` (~20 lines). Each subcommand passes its `--agent` value (which Typer resolves from CLI flag or env var) as `cli_value`. Levels 3-4 are resolved by reading TOML files with `tomlkit` (already a dependency).

The `--agent` option is per-command, defined on each command that launches an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`) via a shared `AgentOption` annotated type. This allows natural usage like `prothon patterns --agent opencode`. Commands that don't launch a session (`new`, `init`, `promise *`) don't have the option. The `PROTHON_AGENT` environment variable is handled via Typer's `envvar=` parameter on the shared option definition.

Valid backend keys match the registry: `claude-code`, `opencode`. When an invalid key is provided, the error message lists all registered backends. When the resolved backend's binary is missing, the error message includes the backend's `install_hint`.

Config file format examples:

```toml
# pyproject.toml
[tool.prothon]
agent = "opencode"
model = "glm-5"
provider = "z-ai"
```

```toml
# ~/.config/prothon/config.toml
agent = "opencode"
model = "glm-5"
provider = "z-ai"
```

### Model Configuration Contract

When the resolved agent is `opencode`, the user can configure which model and provider opencode uses. opencode requires the `provider/model` format on its `--model` flag (e.g. `--model z-ai/glm-5`). Prothon exposes this as two independent configuration values that are resolved separately and joined at invocation time.

**Model precedence** (first non-empty value wins):

| Priority | Source | Mechanism | Example |
|----------|--------|-----------|---------|
| 1 (highest) | CLI flag | `--model` / `-m` per-command option | `prothon spec --model glm-5` |
| 2 | Environment variable | `PROTHON_MODEL` | `export PROTHON_MODEL=glm-5` |
| 3 | Project config | `[tool.prothon]` in `pyproject.toml` | `model = "glm-5"` |
| 4 | Global config | `~/.config/prothon/config.toml` (respects `$XDG_CONFIG_HOME`) | `model = "glm-5"` |
| 5 (lowest) | Default | None | Defer to opencode's own defaults |

**Provider precedence** (identical chain):

| Priority | Source | Mechanism | Example |
|----------|--------|-----------|---------|
| 1 (highest) | CLI flag | `--provider` / `-p` per-command option | `prothon spec --provider z-ai-coding` |
| 2 | Environment variable | `PROTHON_PROVIDER` | `export PROTHON_PROVIDER=z-ai-coding` |
| 3 | Project config | `[tool.prothon]` in `pyproject.toml` | `provider = "z-ai-coding"` |
| 4 | Global config | `~/.config/prothon/config.toml` (respects `$XDG_CONFIG_HOME`) | `provider = "z-ai-coding"` |
| 5 (lowest) | Default | None | Defer to opencode's own defaults |

**Resolution rules:**

- Both `--model` and `--provider` options are per-command, defined on each session command (`spec`, `design`, `patterns`, `execute`, `compliance`) alongside `--agent`, via shared `ModelOption` and `ProviderOption` annotated types.
- If both model and provider resolve to values, prothon joins them as `provider/model` and passes `--model provider/model` to opencode's `build_command`.
- If `--model` already contains a `/` (e.g. `--model z-ai/glm-5`), it is treated as a complete `provider/model` specifier and `--provider` is ignored.
- If only one of model or provider resolves to a value (and the model value does not contain `/`), prothon exits with an error: `--provider requires --model (and vice versa). Use provider/model format or set both.`
- If neither resolves to a value, opencode is invoked without `--model`, deferring to opencode's own configuration and defaults.
- When the resolved agent is `claude-code`, both options are silently ignored — Claude Code does not support model selection via prothon.
- Resolution is implemented as a `resolve_model(cli_model, cli_provider)` function in `cli.py`, following the same pattern as `resolve_agent()`. Environment variables are handled via Typer's `envvar=` parameter on each option definition.

### Documentation Safety Contract

Documentation files (`docs/SPEC.md`, `docs/DESIGN.md`, `docs/PATTERNS.md`) are protected by two mechanisms:

**Edit guard** — Only four agents may write to documentation files:

| File | Permitted writers |
|------|-------------------|
| `docs/SPEC.md` | spec-writer |
| `docs/DESIGN.md` | design-writer, doc-harmonizer |
| `docs/PATTERNS.md` | patterns-writer, doc-harmonizer |

The doc-harmonizer may only write after presenting proposed amendments to the user and receiving explicit approval. This satisfies the SPEC constraint that no documentation changes may be applied by the doc-harmonizer without user approval.

All other agents (execute, compliance, tech-researcher, and any subagents they spawn) must treat these files as read-only. This is enforced at the skill level — each non-doc agent's skill instructions explicitly state that `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` are read-only and must not be written to.

**Commit-after-write** — Every agent that writes to a documentation file must commit that file immediately after writing. This prevents subsequent agent sessions from accidentally overwriting uncommitted changes.

| Agent | Commits |
|-------|---------|
| spec-writer | `docs/SPEC.md` |
| design-writer | `docs/DESIGN.md` |
| patterns-writer | `docs/PATTERNS.md` |
| doc-harmonizer | whichever doc(s) it amended |

The commit message follows the format `docs: update <FILENAME> via <agent-name>`. No push is performed — the commit is local only.

### Tech Research Contract

The tech-researcher generates reference skills in `.agents/skills/` based on the technology choices in DESIGN.md (serves R36-R39). It runs as a post-write quality gate after any agent modifies DESIGN.md, but only when technology choices have materially changed.

**Trigger condition** — The tech-researcher runs when any agent authorized to modify `docs/DESIGN.md` (design-writer or doc-harmonizer) makes changes to the **Technology Choices** table or the **Key Decisions** table. Changes limited to other sections (Architecture, Interfaces, contracts, etc.) do not trigger it.

**Skip condition** — If the modifying agent only added, removed, or modified content outside the Technology Choices and Key Decisions tables, the tech-researcher is skipped entirely. The responsible agent determines this by inspecting the scope of its own changes before deciding whether to launch the tech-researcher subagent.

### Compliance Report Contract

The compliance checker reads all three documentation levels and all source code, then produces three tables (SPEC compliance, DESIGN compliance, PATTERNS compliance). Each row contains: the checkable statement, a PASS/FAIL/SKIP status, and `file:line` evidence. SKIP indicates a check was not applicable (e.g., no files declared for that category). A summary section reports overall percentage and prioritized action items.

### Adoption Contract

`prothon init` overlays the documentation-driven workflow onto an existing Python project without touching its code, configuration, or git history. It performs the following steps in order:

1. Verifies the current directory is a git repository (exits with error if not).
2. Verifies `docs/SPEC.md` does not exist (exits with error if it does, directing the user to `prothon new` or manual setup).
3. Creates `docs/` directory with empty scaffolds: `SPEC.md`, `DESIGN.md`, `PATTERNS.md` — each containing only markdown section headers, inlined in `scaffold.py`.
4. Creates `AGENTS.md` at the project root with agent instruction content (inlined in `scaffold.py`), plus symlinks: `CLAUDE.md → AGENTS.md`, `GEMINI.md → AGENTS.md`, `AGENT.md → AGENTS.md`.
5. Creates `.agents/skills/` directory for project-specific reference skills.
6. Adds version-bump CI workflow files (GitHub Actions and/or GitLab CI/CD) if not already present.
7. Appends `[tool.prothon.ci]` section to `pyproject.toml` with `auto_version = true` if the section does not already exist.
8. Prints a summary of all created files and suggests `prothon spec` as the next step.

The command must not modify existing source files, dependencies, toolchain configuration, pre-commit hooks, or git history. The command may add CI workflow files and append to `pyproject.toml`.

### Scaffolding Contract

`prothon new` collects six inputs (module name, description, author name, author email, Python version, license) and passes them to Copier's `run_copy()`. The template produces a complete project with: `src/` layout, `pyproject.toml`, pre-commit hooks, CI workflows, git repo with initial commit, agent instruction files, doc scaffolds, `.agents/skills/` directory, and version-bump CI workflows for GitHub Actions and GitLab CI/CD. A `.copier-answers.yml` file is written to enable future `copier update` calls.

The generated `pyproject.toml` includes `[tool.prothon.ci]` with `auto_version = true`.

### Skill Discovery Contract

Bundled skills live in `src/prothon/skills/` as directories containing `SKILL.md`. On every CLI invocation that launches an assistant session, the active backend's `sync_skills()` method symlinks each bundled skill directory into that backend's discovery location. The `skills.sync_skills(target)` function accepts a `target` parameter — each backend passes its own directory:

| Backend | Skill sync target |
|---------|-------------------|
| Claude Code | `~/.claude/skills/` |
| opencode | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) |

Symlinks point directly from the backend's skill directory to the bundled package directory. Each backend maintains its own set of symlinks (no shared central location). The duplication cost is zero since symlinks have no disk footprint.

Project-specific reference skills generated by the tech-researcher live in each project's `.agents/skills/` directory. Both Claude Code and opencode discover `.agents/skills/` natively, so no backend-specific handling is needed for project skills.

### Version Bumping Contract

Automatic semantic versioning is handled entirely in CI workflows. The version bump type is determined by which documentation files changed since the last tag:

| Changed file | Bump type |
|--------------|-----------|
| `docs/SPEC.md` | Major |
| `docs/DESIGN.md` (no SPEC change) | Minor |
| `docs/PATTERNS.md` or source only | Patch |

**Detection mechanism:**

1. **Primary: CI environment variables** — Platform-native SHA references provide the most reliable change detection.
   - GitHub Actions: `github.event.before` (previous SHA) and `GITHUB_SHA` (current SHA)
   - GitLab CI: `CI_COMMIT_BEFORE_SHA` and `CI_COMMIT_SHA`

2. **Fallback: git diff-tree** — When env vars are unavailable (manual triggers, scheduled runs):
   ```bash
   git diff-tree --no-commit-id --name-only -r $BEFORE_SHA $CURRENT_SHA
   ```

**Bump execution:**

Custom implementation in `versioning.py` using existing dependencies:
- `tomlkit` reads/writes `pyproject.toml` version field
- String replacement updates `src/<package>/__init__.py` `__version__`
- `git` module creates annotated tag `v<version>`

No external versioning library is used — semver arithmetic is ~30 lines, and both tomlkit and git subprocess are already available.

**Configuration:**

Scaffolded and adopted projects include a `[tool.prothon.ci]` section in `pyproject.toml`:

```toml
[tool.prothon.ci]
auto_version = true  # Set to false to disable automatic version bumping
```

When `auto_version = false`, the CI workflow skips the bump job entirely.

### CI Workflow Contract

Both `prothon new` and `prothon init` generate version-bump CI workflows for the project's chosen platform(s).

**GitHub Actions** (`.github/workflows/version-bump.yml`):
- Triggers on push to default branch
- Reads `[tool.prothon.ci].auto_version` from `pyproject.toml`
- Detects changed files via `github.event.before` / `GITHUB_SHA`
- Executes bump, commits updated files, pushes tag
- Uses `GITHUB_TOKEN` with `contents: write` permission

**GitLab CI/CD** (`.gitlab-ci.yml` includes version-bump job):
- Triggers on push to default branch
- Reads `[tool.prothon.ci].auto_version` from `pyproject.toml`
- Detects changed files via `CI_COMMIT_BEFORE_SHA` / `CI_COMMIT_SHA`
- Executes bump, commits updated files, pushes tag
- Uses `GITLAB_TOKEN` or project access token

**Workflow behavior:**
- Runs only on the default branch (not feature branches)
- Skips when `auto_version = false`
- Skips when no source or documentation files changed (e.g., README-only changes)
- Creates tag only after successful bump — no tag on failure

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
| Agent selection | 5-level precedence: CLI flag > env var > pyproject.toml > global config > default | Per-command flag; env var only; config file only | Matches universal Python ecosystem convention (uv, ruff, pip, pytest). Typer handles levels 1-2 natively. No new dependencies — tomlkit reads both config sources. |
| Backend registry | Internal dict with `register_backend()` hook | Entry points (`importlib.metadata`); plugin framework (stevedore, pluggy) | Zero third-party consumers exist. Internal dict is zero-overhead, grep-discoverable, and type-safe. Entry point discovery adds import-time cost and failure modes. Migration to entry points later is a 10-line change. |
| Backend protocol scope | 6 members: name, cli_command, install_hint, build_command, sync_skills, env_overrides | Minimal 4 members (current); maximal with interactive/non-interactive mode flag | install_hint enables actionable error messages. env_overrides cleanly separates env var concerns from command construction. Interactive/non-interactive mode flag deferred until execute workflow needs it. |
| Model configuration | Separate `--model` and `--provider` flags joined into opencode's `provider/model` format | Single `--model` accepting `provider/model` only | Separate flags allow setting a project default model and switching providers on the CLI (e.g. `z-ai` vs `z-ai-coding` for the same model). Combined format still accepted in `--model` for convenience. opencode strictly requires `provider/model` — bare model names are rejected. |
| Documentation safety | Skill-level edit guard + commit-after-write | Pre-commit hook file check; filesystem permissions | Skill instructions are the right enforcement layer — they govern agent behavior where the writes happen. Pre-commit hooks run too late (after the damage). Filesystem permissions break the agents that need write access. Commit-after-write is the minimal safeguard against loss from subsequent sessions. |
| Version detection | CI env vars (primary) + git diff-tree (fallback) | git log parsing; file hashes; conventional commits | CI env vars are platform-native and 100% reliable in push/PR events. git diff-tree provides universal fallback when env vars unavailable. Together they cover all CI scenarios without local state management. |
| Version bumping | Custom implementation (tomlkit + subprocess) | bump-my-version; python-semver + custom code | Zero new dependencies — tomlkit and subprocess are already available. Semver arithmetic is ~30 lines. Full control over commit/tag format. Adding a library would save minimal code while introducing a dependency. |
| CI configurability | Basic toggle (`auto_version = true/false`) | No config; full branch/trigger configurability | "Minorly configurable" per SPEC. Single toggle lets users disable without deleting files. Branch/trigger customization belongs in the workflow YAML itself — users comfortable with CI can edit directly. |
