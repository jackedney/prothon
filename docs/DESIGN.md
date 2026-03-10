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
    skills/             # Bundled skill assets (non-Python, 8 directories)

template/               # Bundled Copier project template (Jinja2), at project root
```

This layout is driven by the number of subsystems in the SPEC (scaffolding, doc agents, execution, compliance, promise system, versioning, skill management — requirements 1-9, 22, 27-28, 34-37, 42-50, 54) each mapping to one module. At the expected scale of 2-5 KLOC, flat is navigable without namespace overhead.

### Module Dependencies

```
cli.py
  ├── scaffold.generate(), init_existing()
  ├── assistant.get_backend(), launch()
  └── promise.load_promise(), plan(), check_task(), status(), complete_task(), record_attempt(), cleanup()

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

`cli.py` is the only module that depends on Typer for command definitions. Domain modules (`scaffold.py`, `promise.py`, `versioning.py`, etc.) are plain Python and independently testable without invoking the CLI framework. This separation serves requirement 51 (all workflows invocable via CLI) while keeping domain logic framework-independent.

### Bundled Assets

Two non-Python asset directories are bundled with the project:

- `skills/` — 8 bundled skill directories inside the package, each containing a `SKILL.md`. Discovered at runtime via `Path(__file__).parent / "skills"`. Serves requirements 54 (skills bundled with package) and 22 (dedicated interactive agents).
- `template/` — Copier project template at the repository root (not inside the package), with `copier.yml`, Jinja2-templated files, and post-generation tasks. Serves requirements 1-9 (project scaffolding).

`skills/` is included automatically as part of the `src/prothon` package. `template/` is included via `[tool.hatch.build.targets.wheel.force-include]` since it lives outside the package root.

### Assistant Abstraction

Each assistant backend encapsulates its binary name, invocation flags, skill sync target, environment overrides, and command construction. A shared launch lifecycle handles: binary detection, skill syncing, environment merging, subprocess execution, and return code checking.

AI coding CLIs fall into two structural categories based on how they receive skill instructions:

- **Category A (native skill directories)** — Claude Code, opencode, and Gemini CLI have filesystem-based skill discovery. Prothon symlinks bundled skills into their discovery directory and invokes them by name (via slash commands or prompts).
- **Category B (prompt injection)** — Tools like Codex CLI, Goose, and Aider have no native skill directory. Skill content must be injected into the prompt or written to a backend-specific instruction file. These are out of scope per the SPEC but the abstraction accommodates them for future expansion.

A registry maps assistant names to backend classes. Claude Code, opencode, and Gemini CLI are registered. Adding a new assistant requires one backend implementation (~15-25 lines) and one registry entry. No caller changes needed. A `register_backend()` function provides a public extension hook for programmatic use and testing. Entry points are deferred until third-party demand materialises. This serves requirements 52-53 (Claude Code and opencode support, assistant selection).

### Promise Verification

The promise system uses typed dataclass models (`Task`, `Metadata`, `Promise`) to represent the change contract declared in `docs/change_promise.toml`. Verification logic lives in a standalone `check_task()` function that accepts a `GitDiffProvider` protocol, enabling subprocess-free testing with a fake implementation.

Verification checks file existence (for creates/removes), git diff analysis (for modifications), and line count tolerance (+-30% or +-30 lines, whichever is greater). Per-file `FileCheckDetail` results provide structured error data for programmatic consumers. This serves requirements 27-33 (execution verification) and 34-37 (compliance verification).

### Task Lifecycle

Each task in the execute workflow follows this lifecycle:

1. **Dependency check** — wait for all tasks in `dependencies` to be marked complete.
2. **Read context** — read `doc_sections`, `reference_skills`, and `context_files`.
3. **Implement** — create, modify, or remove files per the plan.
4. **Quality gate (R32)** — stage all task files (`git add`), then run `pre-commit run --all-files --show-diff-on-failure`. If hooks auto-fix files, re-stage and re-run once. If hooks still fail, enter the retry loop.
5. **Commit** — `git commit --no-verify` (hooks already ran explicitly in step 4; `--no-verify` avoids double execution).
6. **Plan verification (R31)** — run `check_task()` which uses `git diff <base_commit>` (requires committed changes, so this must follow the commit step).
7. **Completion** — mark the task complete via `complete_task()`.

If step 4 or step 6 fails, the subagent increments its attempt counter and retries from step 3. If `attempts >= max_attempts`, the subagent reports failure to the orchestrator, which asks the user to skip, retry (reset counter), or abort.

Pre-commit hooks run with `--all-files` rather than scoped to declared task files because a task modifying one file may break checks in files that import from it. This matches what a real `git commit` would trigger, satisfying R32's requirement to run "the project's pre-commit hooks."

### Retry Configuration (R33)

The `max_attempts` value is resolved via a two-level precedence:

| Priority | Source | Mechanism |
|----------|--------|-----------|
| 1 (highest) | Per-task override | `max_attempts` field in `[[tasks]]` section of `change_promise.toml` |
| 2 | Project default | `[tool.prothon].max_attempts` in `pyproject.toml` |
| 3 (lowest) | Hardcoded default | `3` |

When the executor creates the promise file, it reads `[tool.prothon].max_attempts` and sets it as the default for each task. The planning agent can override `max_attempts` on specific tasks (e.g., a complex migration task might get 5 attempts while a simple file rename gets 2).

Retry enforcement lives in the skill prompt — the subagent reads `max_attempts` from the promise file and bounds its retry loop accordingly. Programmatic enforcement (an `attempt_task()` function that increments under file lock) can be added later if stricter guarantees are needed.

### Concurrency

Because independent tasks can run in parallel (per requirements 28 and 30), `complete_task()` uses exclusive file locking (`fcntl.flock`) on a sibling `.toml.lock` file to prevent lost updates when concurrent subagents mark tasks complete simultaneously. The lock covers the load → modify → save cycle so no completion is overwritten.

## Technology Choices

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint-driven parameter inference | R51: CLI-invocable workflows | click, argparse |
| copier (>=9.0) | Project templating with native `copier update` support | R1-R9: project scaffolding, R10-R17: project adoption | cookiecutter, custom Jinja2 |
| tomlkit (>=0.13,<1.0) | TOML read/write with comment and formatting preservation | R27-R28: change promise contract | tomllib+tomli-w, toml |
| rich (via typer) | Table rendering for promise plans, status, and compliance reports | R35: compliance report with PASS/FAIL/SKIP status | tabulate, click echo/style |
| subprocess (stdlib) | Git CLI interaction via thin typed wrapper | R7: git init, R31: promise verification | GitPython, pygit2, dulwich |

### Rationale

**Typer** — Already in use. Lowest boilerplate for 12 commands across two nesting levels. Type hints drive parameter inference. Rich-formatted help output included. Actively maintained (v0.24.1, Feb 2026). If ever abandoned, migration to raw Click is mechanical since Typer generates Click objects internally.

**Copier** — Template updating via `copier update` with 3-way merge is central to prothon's value proposition. When prothon's template evolves, existing projects pull in changes without losing local modifications. Clean Python API (`run_copy`, `run_update`, `run_recopy`) designed for library embedding. Declarative prompts with types, validation, and conditions. Neither cookiecutter nor custom Jinja2 provides template updating.

**tomlkit** — `change_promise.toml` is a human-authored contract. When prothon programmatically updates fields like `completed` or `attempts`, it must not destroy comments, spacing, or ordering. Only tomlkit preserves these on roundtrip. Rich document construction helpers (`comment()`, `table()`, `aot()`) enable scaffolding well-formatted TOML from scratch. Maintained by the Poetry organization. The 18x parsing slowdown vs tomllib is irrelevant for small config files.

**Rich** — Already installed at zero marginal cost (Typer unconditionally depends on it). Best-in-class table rendering with per-cell styling, colored PASS/FAIL, and column alignment. Using it for promise plans, status, and compliance reports is free. Interactive prompts remain on `typer.prompt()`.

**subprocess for git** — Every git operation prothon needs maps to a single CLI command with a machine-readable output flag (`--numstat`, `--name-only`, `--porcelain`). No operation benefits from in-process git access. Zero dependencies. `--numstat` (critical for promise verification) is trivial via subprocess but problematic with dulwich. List-form arguments with `GIT_TERMINAL_PROMPT=0` provide a minimal attack surface.

## Interfaces

### CLI Commands

All commands that launch an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) accept a per-command `--agent` / `-a` option and the `PROTHON_AGENT` environment variable. When the resolved agent is `opencode`, `--model` / `-m` and `--provider` / `-p` options control which model is used. See the Agent Configuration Contract and Model Configuration Contract below for the full resolution chains.

| Command | Input | Output | Subsystem |
|---------|-------|--------|-----------|
| `prothon new` | Interactive prompts: module name, description, author name, email, Python version, license | Scaffolded project directory with git repo | scaffold.py |
| `prothon init` | None (validates cwd) | `docs/` scaffolds, `AGENTS.md`, agent symlinks, `.agents/skills/` | scaffold.py |
| `prothon spec` | None (launches interactive session) | Populated `docs/SPEC.md` | cli.py → assistant.py (skill subprocess) |
| `prothon design` | None (launches interactive session) | Populated `docs/DESIGN.md` + generated reference skills | cli.py → assistant.py (skill subprocess) |
| `prothon patterns` | None (launches interactive session) | Populated `docs/PATTERNS.md` | cli.py → assistant.py (skill subprocess) |
| `prothon execute` | None (reads docs, plans, launches subagents) | Implemented code, committed per-task | cli.py → assistant.py (skill subprocess) |
| `prothon compliance` | None (reads docs and code) | Compliance report table (PASS/FAIL per requirement) | cli.py → assistant.py (skill subprocess) |
| `prothon refactor` | None (reads docs, plans, launches subagents) | Refactored code and/or docs, committed per-task | cli.py → assistant.py (skill subprocess) |
| `prothon promise plan` | None (reads `change_promise.toml`) | Pretty-printed task table | promise.py |
| `prothon promise status` | None (reads `change_promise.toml`) | Task completion progress table | promise.py |
| `prothon promise check N` | Zero-based task index | Verification report (per-file PASS/FAIL) | promise.py |
| `prothon promise complete N` | Zero-based task index | Updated `change_promise.toml` (marks task complete) | promise.py |
| `prothon promise record-attempt N` | Zero-based task index | Updated `change_promise.toml` (increments attempt counter) | promise.py |
| `prothon promise cleanup` | None | Removes `change_promise.toml` | promise.py |

### Promise Contract Format

`docs/change_promise.toml` — the contract between the planning phase and execution phase of `prothon execute`.

```
[metadata]
base_commit = "<SHA at plan time>"
created_at = "<ISO 8601>"

[[tasks]]
title = "<task identifier>"
task_id = "<unique hex identifier>"
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
dependencies = [<zero-based-task-index>, ...]
completed = <bool>
attempts = <int>
max_attempts = <int>
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
- `subagent_type_map` — returns a dict mapping canonical agent type names (used in skills) to backend-specific names. Skills reference canonical names; the backend translates at invocation time.

Registered backends:

| Key | Backend | Binary | Skill sync target | Category |
|-----|---------|--------|-------------------|----------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` | A (native skills) |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) | A (native skills) |
| `gemini-cli` | Gemini CLI | `gemini` | `~/.gemini/skills/` | A (native skills) |

Canonical-to-backend subagent type mapping:

| Canonical name | Claude Code | opencode | Gemini CLI |
|---------------|-------------|----------|------------|
| `general-purpose` | `general-purpose` | `general` | `generalist` |
| `explore` | `Explore` | `explore` | `codebase_investigator` |
| `plan` | `Plan` | `plan` | `generalist` |

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

The `--agent` option is per-command, defined on each command that launches an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) via a shared `AgentOption` annotated type. This allows natural usage like `prothon patterns --agent opencode`. Commands that don't launch a session (`new`, `init`, `promise *`) don't have the option. The `PROTHON_AGENT` environment variable is handled via Typer's `envvar=` parameter on the shared option definition.

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

- Both `--model` and `--provider` options are per-command, defined on each session command (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) alongside `--agent`, via shared `ModelOption` and `ProviderOption` annotated types.
- If both model and provider resolve to values, prothon joins them as `provider/model` and passes `--model provider/model` to opencode's `build_command`.
- If `--model` already contains a `/` (e.g. `--model z-ai/glm-5`), it is treated as a complete `provider/model` specifier and `--provider` is ignored.
- If only one of model or provider resolves to a value (and the model value does not contain `/`), prothon exits with an error: `--provider requires --model (and vice versa). Use provider/model format or set both.`
- If neither resolves to a value, opencode is invoked without `--model`, deferring to opencode's own configuration and defaults.
- When the resolved agent is `claude-code`, both options are silently ignored — Claude Code does not support model selection via prothon.
- Resolution is implemented as a `resolve_model(cli_model, cli_provider)` function in `cli.py`, following the same pattern as `resolve_agent()`. Environment variables are handled via Typer's `envvar=` parameter on each option definition.

### Documentation Safety Contract

Documentation files (`docs/SPEC.md`, `docs/DESIGN.md`, `docs/PATTERNS.md`) are protected by two mechanisms:

**Edit guard** — Only five agents may write to documentation files:

| File | Permitted writers |
|------|-------------------|
| `docs/SPEC.md` | spec-writer |
| `docs/DESIGN.md` | design-writer, refactor, doc-harmonizer |
| `docs/PATTERNS.md` | patterns-writer, refactor, doc-harmonizer |

The doc-harmonizer may only write after presenting proposed amendments to the user and receiving explicit approval. This satisfies the SPEC constraint that no documentation changes may be applied by the doc-harmonizer without user approval.

All other agents (execute, compliance, tech-researcher, and any subagents they spawn) must treat these files as read-only. This is enforced at the skill level — each non-doc agent's skill instructions explicitly state that `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` are read-only and must not be written to.

**Commit-after-write** — Every agent that writes to a documentation file must commit that file immediately after writing. This prevents subsequent agent sessions from accidentally overwriting uncommitted changes.

| Agent | Commits |
|-------|---------|
| spec-writer | `docs/SPEC.md` |
| design-writer | `docs/DESIGN.md` |
| patterns-writer | `docs/PATTERNS.md` |
| doc-harmonizer | whichever doc(s) it amended |
| refactor | `docs/DESIGN.md` and/or `docs/PATTERNS.md` |

The commit message follows the format `docs: update <FILENAME> via <agent-name>`. No push is performed — the commit is local only.

**Content constraints** — In addition to edit permissions, PATTERNS.md has content form rules (R25-R26):

- The patterns-writer skill guards must refuse implementation logic in code blocks and limit code examples to function and method signatures (name, parameter types, return types) only.
- The compliance checker includes doc-form verification as part of its SPEC compliance pass, checking PATTERNS.md code blocks against R25-R26 and reporting violations as FAIL rows.
- No runtime enforcement is needed — these are authored content constraints enforced at write-time (patterns-writer guards) and audit-time (compliance checker).

### Tech Research Contract

The tech-researcher generates reference skills in `.agents/skills/` based on the technology choices in DESIGN.md (serves R38-R41). It runs as a post-write quality gate after any agent modifies DESIGN.md, but only when technology choices have materially changed.

**Trigger condition** — The tech-researcher runs when any agent authorized to modify `docs/DESIGN.md` (design-writer, refactor, or doc-harmonizer) makes changes to the **Technology Choices** table or the **Key Decisions** table. Changes limited to other sections (Architecture, Interfaces, contracts, etc.) do not trigger it.

**Skip condition** — If the modifying agent only added, removed, or modified content outside the Technology Choices and Key Decisions tables, the tech-researcher is skipped entirely. The responsible agent determines this by inspecting the scope of its own changes before deciding whether to launch the tech-researcher subagent.

### Compliance Report Contract

The compliance checker reads all three documentation levels and all source code, then produces three tables (SPEC compliance, DESIGN compliance, PATTERNS compliance). Each row contains: the checkable statement, a PASS/FAIL/SKIP status, and `file:line` evidence. SKIP indicates a check was not applicable (e.g., no files declared for that category). A summary section reports overall percentage and prioritized action items.

### SPEC.md Content Contract

SPEC.md is the highest-authority document in the hierarchy. It defines *what* the system must do without prescribing *how*. Its expected sections are:

- **Purpose** — A concise description of what the tool does and why it exists. States the problems it solves.
- **Requirements** — Grouped by subsystem, each requirement is a numbered statement (R1, R2, ...) using "must" language. Requirements must be testable and verifiable — vague aspirations are not requirements.
- **Constraints** — Hard limits on technology, process, or scope that are non-negotiable.
- **Out of Scope** — Explicitly excluded features or capabilities, with optional notes on future consideration.

Content rules:
- No technology choices (package names, frameworks) — those belong in DESIGN.md.
- No architecture or component structure — those belong in DESIGN.md.
- No code patterns or conventions — those belong in PATTERNS.md.
- Requirements must be self-contained — each one should be understandable without reading the others.

### DESIGN.md Content Contract

DESIGN.md is the middle-authority document. It defines *how* the system is built — architecture, technology choices, and interfaces — without specifying code-level patterns. Its expected sections are:

- **Architecture** — High-level component structure, module layout, how components connect and communicate. References which SPEC requirements drive each architectural choice.
- **Technology Choices** — Table format: Package | Purpose | Serves Requirement | Alternatives Considered. Followed by rationale for each choice.
- **Interfaces** — API boundaries, data formats, contracts between components. Defines the "what" of each interface, not the "how." Includes all named contracts (Promise Contract, Backend Contract, etc.).
- **Key Decisions** — Each decision that required research. Format: Decision | Choice | Alternatives | Rationale.

Content rules:
- No code snippets or implementation details — those belong in PATTERNS.md.
- No design patterns (e.g., "use factory pattern") — those belong in PATTERNS.md.
- Every technology choice and architectural decision must trace back to a specific SPEC requirement.
- Nothing may contradict SPEC.md — SPEC has higher authority.

### PATTERNS.md Content Contract

PATTERNS.md defines the code patterns, conventions, and testing approaches for a project. Its content is constrained by R25-R26:

- **Natural language first** — Pattern rationale, behavioral logic, and design decisions must be expressed in prose, not code. Each pattern section explains *what* the pattern achieves, *when* to use it, and *why* it was chosen.
- **Signature-only code examples** — Code blocks in PATTERNS.md are limited to function and method signatures: name, parameter types, and return type. No function bodies, control flow, import blocks, or implementation logic may appear in code form.
- **Design pattern focus** — PATTERNS.md selects and describes Python design patterns suitable for achieving the architecture defined in DESIGN.md. It does not prescribe implementation details — those emerge from the combination of the pattern description and the developer's (or agent's) judgment.

Examples of **allowed** content:
- Prose describing when to use the protocol pattern vs ABC inheritance
- `def check_task(task_index: int, *, diff_provider: GitDiffProvider) -> TaskCheckReport` as a signature example
- A table comparing pattern trade-offs

Examples of **forbidden** content:
- Full function bodies with if/else logic, loops, or error handling
- Import blocks showing how to wire modules together
- Test implementations beyond test function signatures

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

`prothon new` collects six inputs (module name, description, author name, author email, Python version, license) and passes them to Copier's `run_copy()`. The template produces a complete project with: `src/` layout, `pyproject.toml`, pre-commit hooks, CI workflows, git repo with initial commit, `AGENTS.md` with agent instruction content plus symlinks (`CLAUDE.md → AGENTS.md`, `GEMINI.md → AGENTS.md`, `AGENT.md → AGENTS.md`), doc scaffolds, `.agents/skills/` directory, and version-bump CI workflows for GitHub Actions and GitLab CI/CD. A `.copier-answers.yml` file is written to enable future `copier update` calls.

The generated `pyproject.toml` includes `[tool.prothon.ci]` with `auto_version = true`.

### Skill Discovery Contract

Bundled skills live in `src/prothon/skills/` as directories containing `SKILL.md`. On every CLI invocation that launches an assistant session, the active backend's `sync_skills()` method symlinks each bundled skill directory into that backend's discovery location. The `skills.sync_skills(target)` function accepts a `target` parameter — each backend passes its own directory:

| Backend | Skill sync target |
|---------|-------------------|
| Claude Code | `~/.claude/skills/` |
| opencode | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) |

Symlinks point directly from the backend's skill directory to the bundled package directory. Each backend maintains its own set of symlinks (no shared central location). The duplication cost is zero since symlinks have no disk footprint.

Project-specific reference skills generated by the tech-researcher live in each project's `.agents/skills/` directory. Both Claude Code and opencode discover `.agents/skills/` natively, so no backend-specific handling is needed for project skills.

### Skill Authoring Contract

Skills that need to spawn subagents must use **canonical agent type names** from the subagent type mapping table in the Assistant Backend Contract. Skills must NOT reference tool-specific APIs (e.g., `Task tool, subagent_type: general-purpose`). Instead, skills must use a standardized instruction format:

> Spawn a subagent (type: `general-purpose`, fresh context) with this prompt: ...

The canonical format is: `Spawn a subagent (type: <canonical-name>, fresh context) with this prompt:` followed by the prompt content. Each assistant's LLM is responsible for translating this instruction into its native tool call (Claude Code's `Agent` tool, opencode's `task` tool). The canonical names are documented in the subagent type mapping table.

Skill frontmatter fields that are assistant-specific (`context: fork`, `model: sonnet`, `agent:`) are **Claude Code extensions** — opencode silently ignores them. Skills must not depend on these fields for correct behavior. Any skill that needs subagent isolation must use the explicit "Spawn a subagent" instruction pattern instead.

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
- Triggers on `pull_request` events (`opened`, `synchronize`) targeting the default branch
- Reads `[tool.prothon.ci].auto_version` from `pyproject.toml`
- Detects changed files via `git diff origin/<default-branch>...HEAD`
- Computes the next version from the base branch version, commits bump to the PR branch
- Idempotent: skips if the PR branch already has the correct version
- Uses `GITHUB_TOKEN` with `contents: write` permission (no PAT required)

**GitHub Actions** (`.github/workflows/version-tag.yml`):
- Triggers on push to default branch (i.e., after PR merge)
- Creates an annotated `v<version>` tag from the version in `pyproject.toml`
- Skips if the tag already exists
- Uses `GITHUB_TOKEN` with `contents: write` permission

**GitLab CI/CD** (`.gitlab-ci.yml` includes version-bump job):
- Triggers on push to default branch
- Reads `[tool.prothon.ci].auto_version` from `pyproject.toml`
- Detects changed files via `CI_COMMIT_BEFORE_SHA` / `CI_COMMIT_SHA`
- Executes bump, commits updated files, pushes tag
- Uses `GITLAB_TOKEN` or project access token

**Workflow behavior:**
- Version bump runs on PR branches targeting the default branch, not on the default branch itself
- Skips when `auto_version = false`
- Skips when no source or documentation files changed (e.g., README-only changes)
- Parallel PRs may compute the same next version; squash merge will create a pyproject.toml conflict on the second PR, requiring a branch update which re-triggers the bump with the correct base version
- Tag is created post-merge only after the version lands on the default branch

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
| Backend protocol scope | 7 members: name, cli_command, install_hint, build_command, sync_skills, env_overrides, subagent_type_map | Minimal 4 members (current); maximal with interactive/non-interactive mode flag | install_hint enables actionable error messages. env_overrides cleanly separates env var concerns from command construction. subagent_type_map enables cross-assistant skill portability. Interactive/non-interactive mode flag deferred until execute workflow needs it. |
| Model configuration | Separate `--model` and `--provider` flags joined into opencode's `provider/model` format | Single `--model` accepting `provider/model` only | Separate flags allow setting a project default model and switching providers on the CLI (e.g. `z-ai` vs `z-ai-coding` for the same model). Combined format still accepted in `--model` for convenience. opencode strictly requires `provider/model` — bare model names are rejected. |
| Documentation safety | Skill-level edit guard + commit-after-write | Pre-commit hook file check; filesystem permissions | Skill instructions are the right enforcement layer — they govern agent behavior where the writes happen. Pre-commit hooks run too late (after the damage). Filesystem permissions break the agents that need write access. Commit-after-write is the minimal safeguard against loss from subsequent sessions. |
| Version detection | CI env vars (primary) + git diff-tree (fallback) | git log parsing; file hashes; conventional commits | CI env vars are platform-native and 100% reliable in push/PR events. git diff-tree provides universal fallback when env vars unavailable. Together they cover all CI scenarios without local state management. |
| Version bumping | Custom implementation (tomlkit + subprocess) | bump-my-version; python-semver + custom code | Zero new dependencies — tomlkit and subprocess are already available. Semver arithmetic is ~30 lines. Full control over commit/tag format. Adding a library would save minimal code while introducing a dependency. |
| CI configurability | Basic toggle (`auto_version = true/false`) | No config; full branch/trigger configurability | "Minorly configurable" per SPEC. Single toggle lets users disable without deleting files. Branch/trigger customization belongs in the workflow YAML itself — users comfortable with CI can edit directly. |
| Subagent invocation in skills | Canonical names with per-backend mapping | Tool-specific instructions per assistant; backend-specific skill variants | Single set of skills works across both backends. Canonical names are translated by each backend's `subagent_type_map`. Backend-specific variants would double maintenance. Tool-specific instructions (e.g., `Task tool, subagent_type:`) break when the other assistant has a different tool API. |
| Skill frontmatter portability | Assistant-specific fields ignored by non-supporting backends | Require all backends to support all fields; strip unsupported fields at sync time | opencode silently ignores unknown frontmatter (`context: fork`, `model:`). Requiring support would block backend addition. Stripping adds complexity for zero benefit since unknown fields are already harmless. |
| Task quality gate | `pre-commit run --all-files` replacing `poe check` | `poe check`; hooks as part of `git commit` (no `--no-verify`); scoped `--files` | Pre-commit is a superset of `poe check` (adds trailing-whitespace, end-of-file-fixer, check-yaml, auto-fixing). Explicit hook run before commit gives parseable output and handles auto-fixes cleanly. `--all-files` catches cross-file regressions. `--no-verify` on commit avoids double execution. |
| Retry configuration | Project default in `[tool.prothon].max_attempts` + per-task override in promise TOML | CLI flag; env var; promise metadata section | Two-level resolution (project + per-task) follows existing config patterns. Retry count doesn't warrant CLI flag or env var precedence levels. Per-task override lets the planning agent adjust for task complexity. |
| Retry enforcement | Skill prompt reads `max_attempts` from promise file | Programmatic `attempt_task()` with file locking; hybrid skill + validation | Skill prompt already manages the retry loop. Reading `max_attempts` from the promise file is the minimal change. Programmatic enforcement can be added later if stricter guarantees are needed. |
| PATTERNS.md content form | Signature-only code, natural language rationale | Allow full code examples; no code at all | Signatures communicate interface contracts without prescribing implementation. Full code examples drift from actual implementations and constrain developer judgment. No code at all loses the precision of typed signatures. |
| Documentation content contracts | Explicit section structure and content rules for all three doc levels | Implicit via skill instructions only; single combined contract | Each doc level has distinct content rules (SPEC: no tech choices; DESIGN: no code; PATTERNS: no implementation logic). Explicit contracts make the hierarchy self-describing and enable compliance checking. Per-level contracts are clearer than a single combined contract. |
