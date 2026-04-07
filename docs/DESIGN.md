# Design Document

## Architecture

### Module Structure

Mostly flat module layout under `src/prothon/`, with one subpackage (`checks/`) grouping static compliance checks. CLI definitions and logic are distributed across dedicated modules for commands, UI, and configuration.

```text
src/prothon/
    __init__.py
    adoption.py         # Project adoption: overlaying docs-first workflow onto existing projects
    adoption_templates.py  # Templates and scaffolds used during project adoption
    ast_miner.py        # AST pattern mining and library idiom recognition (FastAPI, Typer, Pydantic)
    assistant.py        # Backend registry, protocol, and launch lifecycle for AI assistants
    cli.py              # Typer app and command definitions
    commands.py         # Implementation logic for CLI commands (delegates to domain modules)
    ui.py               # Rich-based terminal UI, tables, and status reporting
    config.py           # Multi-level configuration resolution (CLI, env, toml)
    checks/             # Static compliance checks subpackage (split from static_checks.py)
        __init__.py     # Re-exports run_static_checks and all public check functions
        utils.py        # AST analysis, signature helpers
        docs.py         # Document-related checks (R24-R26)
        structure.py    # Package structure checks (R3-R5, R15)
        workflows.py    # Execute/refactor workflow checks (R27-R42)
        research.py     # Tech researcher and versioning checks (R43-R55)
        adoption.py     # Adoption intelligence check (R13)
    compliance.py       # Compliance data types (CheckResult, CheckStatus, ComplianceReport)
    exceptions.py       # Custom exception hierarchy
    git.py              # Thin typed wrapper around git CLI via subprocess
    models.py           # Shared data models (Task, Metadata, Promise) for the promise system
    promise.py          # Promise TOML I/O and lifecycle management
    promise_verify.py   # Git diff analysis and task verification logic
    project.py          # Project root detection, shared project context
    refactor.py         # Drift discovery and refactor promise generation
    scaffold.py         # Template rendering, copier answers, project adoption
    scaffold_cli.py     # Scaffolding-specific CLI commands and interactive prompts
    skills.py           # Skill discovery, symlink management
    versioning.py       # Semantic version detection, bumping, git tagging
    skills/             # Bundled skill assets (non-Python, 8 directories)

template/               # Bundled Copier project template (Jinja2), at project root
```

This layout is driven by the number of subsystems in the SPEC (scaffolding, adoption, doc agents, execution, compliance, promise system, refactor, tech research, versioning, skill management — requirements 1-17, 22, 27-37, 38-61) each mapping to one or more modules. The `checks/` subpackage is the single exception to the flat layout — it groups 28+ static check functions that would otherwise form an 850+ line monolith.

### Module Dependencies

```text
cli.py
  ├── commands.*
  ├── scaffold_cli.new_project(), init_project()
  ├── assistant._BACKENDS
  └── project.find_project_root()

commands.py
  ├── assistant.get_backend(), launch()
  ├── config.resolve_agent(), resolve_model(), file_hash(), find_init_path(), ...
  ├── git.commit_file(), is_dirty()
  ├── models.PROMISE_PATH
  ├── promise.*, promise_verify.*, versioning.*
  ├── project.find_project_root()
  ├── checks.run_static_checks()
  └── ui.render_check_report(), render_compliance_report(), render_plan(), render_status()

adoption.py
  ├── adoption_templates.* (scaffold strings)
  ├── ast_miner.ASTPatternMiner
  ├── scaffold.get_template_dir()
  └── git.run_git()

checks.*
  └── compliance.CheckResult, CheckStatus, CheckType, ComplianceReport, Requirement

scaffold_cli.py
  └── scaffold.generate(), init_existing()

promise.py
  ├── models.Task, Metadata, Promise, PROMISE_PATH
  └── promise_verify.check_task()

assistant.py
  └── skills.sync_skills(target)

versioning.py
  ├── git.* (for tag operations)
  └── tomlkit (for version file updates)
```

All modules
  ├── project.find_project_root()
  ├── git.*
  └── exceptions.*
```

`cli.py` is the only module that depends on Typer for command definitions. Domain modules (`scaffold.py`, `promise.py`, `versioning.py`, etc.) are plain Python and independently testable without invoking the CLI framework. This separation serves requirement 56 (all workflows invocable via CLI) while keeping domain logic framework-independent.

### Bundled Assets

Two non-Python asset directories are bundled with the project:

- `skills/` — 8 bundled skill directories inside the package, each containing a `SKILL.md`. Discovered at runtime via `Path(__file__).parent / "skills"`. Serves requirements 59 (skills bundled with package) and 22 (dedicated interactive agents).
- `template/` — Copier project template at the repository root (not inside the package), with `copier.yml`, Jinja2-templated files, and post-generation tasks. Serves requirements 1-9 (project scaffolding).

`skills/` is included automatically as part of the `src/prothon` package. `template/` is included via `[tool.hatch.build.targets.wheel.force-include]` since it lives outside the package root.

### Assistant Abstraction

Each assistant backend encapsulates its binary name, invocation flags, skill sync target, environment overrides, and command construction. A shared `launch()` lifecycle handles common environment setup (binary detection, skill syncing, environment merging, subprocess execution, and return code checking) while delegating skill delivery to category-specific backend strategies. Gemini CLI is configured to run in YOLO mode by default to ensure automated execution of suggested actions during autonomous workflows.

AI coding CLIs fall into two structural categories based on how they ingest skills:

- **Category A (native skill directories)** — Claude Code, opencode, Gemini CLI, and OB1 have filesystem-based skill discovery. Prothon symlinks bundled skills into their discovery directory and invokes them by name (via slash commands or prompts).
- **Category B (prompt injection)** — Tools like Codex CLI, Goose, and Aider have no native skill directory. Skill content must be injected into the prompt or written to a backend-specific instruction file. No Category B backends are currently registered; the abstraction accommodates them for future expansion.

A registry maps assistant names to backend classes. Claude Code, opencode, and Gemini CLI are registered. Adding a new assistant requires one backend implementation (~15-25 lines) and one registry entry. No caller changes needed. A `register_backend()` function provides a public extension hook for programmatic use and testing. Entry points are deferred until third-party demand materialises. This serves requirements 57-58 (Claude Code, opencode, and Gemini CLI support; assistant selection).

### Promise Verification

The promise system uses typed dataclass models (`Task`, `Metadata`, `Promise`) to represent the change contract declared in `docs/change_promise.toml`. Verification logic lives in `promise_verify.py` via a standalone `check_task()` function that accepts a `GitDiffProvider` protocol, enabling subprocess-free testing with a fake implementation.

Verification checks file existence (for creates/removes), git diff analysis (for modifications), and line count tolerance (+-30% or +-30 lines, whichever is greater). Per-file `FileCheckDetail` results provide structured error data for programmatic consumers.

**Flexible Scope:** Verification allows the agent to modify files not explicitly declared in the task's `files_to_modify` if those changes are necessary to satisfy the quality gate (R32). This is a deliberate extension of R31's strict plan-verification scope — R32 requires that pre-commit hooks pass after each task, which may necessitate fixes to files outside the task's declared scope (e.g., linting fixes in imports, formatting in adjacent code). This serves requirements 27-33 (execution verification) and 34-37 (compliance verification).

### Task Lifecycle

Each task in the execute workflow follows this lifecycle:

1. **Dependency check** — wait for all tasks whose `task_id` appears in this task's `dependencies` list to be marked complete.
2. **Read context** — read `doc_sections`, `reference_skills`, and `context_files`.
3. **Implement** — create, modify, or remove files per the plan.
4. **Quality gate (R32)** — run `pre-commit run --all-files`. The agent must fix all reported errors and warnings project-wide (including pre-existing ones) before proceeding.
5. **Commit** — Stage only files declared in `files_to_create`, `files_to_modify`, and `files_to_remove`, plus any files auto-fixed by the quality gate in step 4. Then commit with `--no-verify`. Note: `--no-verify` is safe because step 4 already ran the full hook suite.
6. **Plan verification (R31)** — run `check_task()` which uses `git diff <base_commit>`.
7. **Completion** — mark the task complete via `complete_task()`.

If step 4 or step 6 fails, the subagent calls `record_attempt()` and retries from step 3. The retry is gated by `record_attempt()` succeeding — if `attempts >= max_attempts`, `record_attempt()` raises `MaxAttemptsExceeded` rather than incrementing, which halts the retry loop. The orchestrator then asks the user to skip, retry (reset counter), or abort.

### Compliance Checker (R34–37)

The compliance checker is a hybrid verification engine that maps requirements from SPEC, DESIGN, and PATTERNS to source code evidence. It uses a three-tier evidence gathering strategy:

- **Static Analysis (Regex/AST):** Deterministic checks for structural requirements (e.g., base class inheritance, type hint usage) and documentation form rules (e.g., signature-only code in PATTERNS.md).
- **Semantic Analysis (LLM):** Targeted subagents verify high-level requirements that cannot be proven through static analysis.
- **Evidence Mapping:** Every check produces a `CheckResult` with a tri-state status (PASS, FAIL, SKIP) and `file:line` evidence.

### Refactor Workflow

The refactor workflow facilitates the evolution of the project by identifying and resolving drift or opportunities for improvement. It operates in two waves to ensure documentation is improved before code is aligned to it.

- **Wave 0 — Documentation Quality:** Before examining code drift, the workflow evaluates whether DESIGN.md and PATTERNS.md are still optimal given how the project has grown. This serves R40's mandate for "proactive optimization opportunities." Wave 0 uses a hybrid approach: programmatic evidence gathering (module metrics, pattern usage analysis, cross-module similarity detection) feeds into LLM-driven analysis that evaluates design decisions and pattern quality. Wave 0 produces only documentation changes (DESIGN → PATTERNS). After Wave 0 completes, the doc-harmonizer runs automatically to ensure cross-document consistency.
- **Wave 1 — Code Drift:** The existing code-level discovery (doc hierarchy gaps, patterns compliance, large files, missing tests) runs against the *updated* documentation from Wave 0, ensuring code changes align with the improved design rather than the original.
- **Refactor Wave:** Within each wave, changes flow from **DESIGN -> PATTERNS -> CODE**. Architectural shifts must be documented before code is modified.
- **Execution Phase:** Orchestrates implementation tasks using self-correcting subagent loops to align the project with the updated documentation.

### Doc-Harmonizer (R24)

The doc-harmonizer maintains internal consistency across the documentation hierarchy.

- **Semantic Cross-Referencing:** Uses LLM-based analysis to detect contradictions and scope creep (e.g., DESIGN introducing requirements that belong in SPEC).
- **Top-Down Enforcement:** Validates that lower-authority documents do not contradict higher-authority ones.
- **Approval Workflow:** Presents proposed amendments as "Before/After" diffs for user approval before applying changes.

### Tech-Researcher (R43-46)

The tech-researcher refreshes project-specific reference skills based on the technology choices in DESIGN.md (serves R43-46).

- **Sourcing:** Combines local inspection (`uv pip show`, `inspect`) with direct web fetching (`web_fetch` on official doc URLs) to ensure version accuracy and up-to-date idiomatic knowledge.
- **Progressive Disclosure:** Skills use a three-level system to minimize token usage:
  - **Level 1 (YAML frontmatter):** Includes name, description, and trigger phrases in `SKILL.md`. Loaded into the system prompt for discovery.
  - **Level 2 (SKILL.md body):** Core instructions, best practices, and "When to use" guidance (max 500 words).
  - **Level 3 (Linked files):** Deep technical references, API guides, and complex examples moved to a `references/` directory.
- **Multi-File Skills:** Generates skills as directories in `.agents/skills/` using standard naming: `SKILL.md` (case-sensitive) and kebab-case folder names.
- **Discovery:** Leverages the assistant's ability to load only the necessary context, keeping the core `SKILL.md` concise.

### Adoption Intelligence (R13)

During `prothon init`, the system uses Python's `ast` module to scan for high-signal structural elements in existing code, pre-populating `PATTERNS.md` with existing conventions.

- **AST Pattern Miner:** Uses Python's built-in `ast` module to scan for high-signal structural elements (base classes, protocols, common decorators).
- **Idiom Matcher:** Includes pre-defined signatures for popular libraries (FastAPI, Typer, Pydantic).
- **Signature-Only Extraction:** Satisfies the "signature-only" constraint (R25-R26) by using `ast.unparse()` on discovered nodes after clearing their implementation bodies.
- **Local Execution:** Runs entirely offline and locally during the adoption workflow.

### Mutation Testing CI (R6)

Mutation testing is integrated as an asynchronous, non-blocking audit to avoid slowing down the development cycle.

- **Non-blocking Job:** Configured with `continue-on-error: true` (GitHub) or `allow_failure: true` (GitLab).
- **Artifacts:** Produces `mutants/mutmut-stats.json` for analysis, serving as a durable record of test suite effectiveness.

### Retry Configuration (R33)

The `max_attempts` value is resolved via a two-level precedence:

| Priority | Source | Mechanism |
|----------|--------|-----------|
| 1 (highest) | Per-task override | `max_attempts` field in `[[tasks]]` section of `change_promise.toml` |
| 2 | Project default | `[tool.prothon].max_attempts` in `pyproject.toml` |
| 3 (lowest) | Hardcoded default | `3` |

When the executor creates the promise file, it reads `[tool.prothon].max_attempts` and sets it as the default for each task. The planning agent can override `max_attempts` on specific tasks (e.g., a complex migration task might get 5 attempts while a simple file rename gets 2).

Retry enforcement operates at two levels:

1. **Skill-prompt compliance** — the subagent reads `max_attempts` from the promise file and bounds its retry loop accordingly.
2. **Programmatic backstop** — `record_attempt()` must refuse to increment when `attempts >= max_attempts`, raising a `MaxAttemptsExceeded` error. This provides a programmatic backstop independent of skill-prompt compliance.

### Concurrency

Because independent tasks can run in parallel (per requirements 28 and 30), `complete_task()` uses platform-specific exclusive file locking on a sibling `.toml.lock` file to prevent lost updates when concurrent subagents mark tasks complete simultaneously. The lock covers the load → modify → save cycle so no completion is overwritten.

## Technology Choices

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint-driven parameter inference | R56: CLI-invocable workflows | click, argparse |
| uv (>=0.1) | Package management and project environment isolation | R4: fixed dev toolchain | pip, poetry, conda |
| poethepoet (>=0.25) | Task runner for project-wide quality checks (`poe check`) | R4: fixed dev toolchain | make, invoke, just |
| copier (>=9.0) | Project templating with native `copier update` support | R1-R9: project scaffolding, R10-R17: project adoption | cookiecutter, custom Jinja2 |
| tomlkit (>=0.13,<1.0) | TOML read/write with comment and formatting preservation | R27-R28: change promise contract | tomllib+tomli-w, toml |
| rich (via typer) | Table rendering for promise plans, status, and compliance reports | R35: compliance report with PASS/FAIL/SKIP status | tabulate, click echo/style |
| subprocess (stdlib) | Git CLI interaction via thin typed wrapper | R7: git init, R31: promise verification | GitPython, pygit2, dulwich |
| claude-code | AI assistant backend | R57: Claude Code support | opencode, gemini, ob1 |
| opencode | AI assistant backend | R57-R58, R61: opencode support | claude-code, gemini, ob1 |
| gemini-cli | AI assistant backend | R57: Gemini CLI support | claude-code, opencode, ob1 |
| jinja2 (>=3.1) | Template rendering for adoption scaffolds (AGENTS.md, doc stubs) | R13-R16: project adoption | string.Template, mako |
| ob1 | AI assistant backend | R57: OB1 support (pluggable) | claude-code, opencode, gemini |

### Rationale

**Typer** — Already in use. Lowest boilerplate for 12 commands across two nesting levels. Type hints drive parameter inference. Rich-formatted help output included. Actively maintained (v0.24.1, Feb 2026). If ever abandoned, migration to raw Click is mechanical since Typer generates Click objects internally.

**uv** — Industry standard for high-performance Python package management. Provides deterministic environments across all project commands, including the execution quality gate.

**poethepoet** — Provides a centralized `check` command that encapsulates the entire quality suite (Ruff, Ty, Pytest, Bandit, Vulture, Complexipy). This ensures the execution agent uses the same standard as CI and human developers.

**Copier** — Template updating via `copier update` with 3-way merge is central to prothon's value proposition. When prothon's template evolves, existing projects pull in changes without losing local modifications. Clean Python API (`run_copy`, `run_update`, `run_recopy`) designed for library embedding. Declarative prompts with types, validation, and conditions. Neither cookiecutter nor custom Jinja2 provides template updating.

**tomlkit** — `change_promise.toml` is a human-authored contract. When prothon programmatically updates fields like `completed` or `attempts`, it must not destroy comments, spacing, or ordering. Only tomlkit preserves these on roundtrip. Rich document construction helpers (`comment()`, `table()`, `aot()`) enable scaffolding well-formatted TOML from scratch. Maintained by the Poetry organization. The 18x parsing slowdown vs tomllib is irrelevant for small config files.

**Rich** — Already installed at zero marginal cost (Typer unconditionally depends on it). Best-in-class table rendering with per-cell styling, colored PASS/FAIL, and column alignment. Using it for promise plans, status, and compliance reports is free. Interactive prompts remain on `typer.prompt()`.

**subprocess for git** — Every git operation prothon needs maps to a single CLI command with a machine-readable output flag (`--numstat`, `--name-only`, `--porcelain`). No operation benefits from in-process git access. Zero dependencies. `--numstat` (critical for promise verification) is trivial via subprocess but problematic with dulwich. List-form arguments with `GIT_TERMINAL_PROMPT=0` provide a minimal attack surface.

**Jinja2** — Already a transitive dependency (Copier depends on it), so adding an explicit pin costs zero additional packages. Used directly in `adoption_templates.py` and `scaffold.py` for rendering AGENTS.md, doc stubs, and CI workflow files during `prothon init` and `prothon new`. `string.Template` lacks conditionals and loop constructs needed for scaffold logic. Mako is a heavier alternative with no advantage given Jinja2 is already present.

## Interfaces

### CLI Commands

All commands that launch an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) accept a per-command `--agent` / `-a` option and the `PROTHON_AGENT` environment variable. When the resolved agent is `opencode`, `--model` / `-m` and `--provider` / `-p` options control which model is used. See the Agent Configuration Contract and Model Configuration Contract below for the full resolution chains.

| Command | Input | Output | Subsystem |
|---------|-------|--------|-----------|
| `prothon new` | Interactive prompts: module name, description, author name, email, Python version, license | Scaffolded project directory with git repo | scaffold_cli.py |
| `prothon init` | None (validates cwd) | `docs/` scaffolds, `AGENTS.md`, agent symlinks, `.agents/skills/` | scaffold_cli.py |
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
dependencies = ["<task_id>", ...]
completed = <bool>
attempts = <int>
max_attempts = <int>
```

### Promise Verification Contract

Each task verification produces a `TaskCheckReport` containing a list of `CheckResult` entries. Each `CheckResult` has a `CheckStatus` enum (members: `PASSED`, `FAILED`, `SKIPPED` with values `"PASS"`, `"FAIL"`, `"SKIP"`), a summary string, and a list of `FileCheckDetail` records providing per-file granularity (path, expected state, actual state, status). SKIPPED indicates a check was not applicable (e.g. no files declared for that category). A report passes if it contains no FAILED entries — SKIPPED results do not affect the outcome.

Dependency resolution uses `task_id` lookup: each entry in a task's `dependencies` list is matched against the `task_id` field of other tasks in the promise file, not against positional indices. This ensures dependencies remain valid when tasks are reordered, inserted, or removed during planning.

Tolerance for line counts: +-30% or +-30 lines, whichever is greater. Binary files are excluded from line counts.

### Assistant Backend Contract

Every assistant backend must satisfy the `AssistantBackend` protocol (structural typing, no inheritance required):

- `name` — human-readable name for error messages (e.g. "Claude Code", "opencode")
- `cli_command` — binary name to look up on PATH (e.g. "claude", "opencode")
- `install_hint` — installation URL or command for actionable error messages when the binary is missing
- `build_command(skill_name, cwd, model=None)` — constructs the subprocess argv for launching a session. The optional `model` parameter is the resolved `provider/model` string (see Model Configuration Contract). Category A backends reference the skill by name via slash commands. Claude Code uses `["claude", "--dangerously-skip-permissions", "/prothon-spec-writer"]`; opencode uses `["opencode", "--prompt", "/prothon-spec-writer"]` with the `--prompt` flag; and Gemini CLI uses `["gemini", "--approval-mode=yolo", "Activate the prothon-spec-writer skill and follow its instructions."]` to enable non-interactive execution via a natural language prompt. When `model` is provided, backends that support it append `["--model", model]` to the argv. Category B backends read skill content and inject it into the prompt argument.
- `sync_skills()` — installs/symlinks bundled skills to the assistant's discovery location. Category A backends call `skills.sync_skills(target=...)` with their specific directory. Category B backends may be a no-op.
- `env_overrides()` — returns a dict of extra environment variables needed for non-interactive execution (e.g. `{"GOOSE_MODE": "auto"}`). Returns an empty dict if none are needed.
- `subagent_type_map` — returns a dict mapping canonical agent type names (used in skills) to backend-specific names. Skills reference canonical names; the backend translates at invocation time.

Registered backends:

| Key | Backend | Binary | Skill sync target | Category |
|-----|---------|--------|-------------------|----------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` | A (native skills) |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`) | A (native skills) |
| `gemini` | Gemini CLI | `gemini` | `~/.gemini/skills/` | A (native skills) |
| `ob1` | OB1 | `ob1` | `~/.ob1/skills/` | A (native skills) |

Canonical-to-backend subagent type mapping:

| Canonical name | Claude Code | opencode | Gemini CLI | OB1 |
|---------------|-------------|----------|------------|-----|
| `general-purpose` | `general-purpose` | `general` | `generalist_agent` | `general` |
| `explore` | `Explore` | `explore` | `codebase_investigator` | `explore` |
| `plan` | `Plan` | `plan` | `generalist_agent` | `plan` |

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

Resolution is implemented as a `resolve_agent(cli_value)` function in `config.py` (~20 lines). Each subcommand passes its `--agent` value (which Typer resolves from CLI flag or env var) as `cli_value`. Levels 3-4 are resolved by reading TOML files with `tomlkit` (already a dependency).

The `--agent` option is per-command, defined on each command that launches an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) via a shared `AgentOption` annotated type. This allows natural usage like `prothon patterns --agent opencode`. Commands that don't launch a session (`new`, `init`, `promise *`) don't have the option. The `PROTHON_AGENT` environment variable is handled via Typer's `envvar=` parameter on the shared option definition.

Valid backend keys match the registry: `claude-code`, `opencode`, `gemini`. When an invalid key is provided, the error message lists all registered backends. When the resolved backend's binary is missing, the error message includes the backend's `install_hint`.

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
- Resolution is implemented as a `resolve_model(cli_model, cli_provider)` function in `config.py`, following the same pattern as `resolve_agent()`. Environment variables are handled via Typer's `envvar=` parameter on each option definition.

### Documentation Safety Contract

Documentation files (`docs/SPEC.md`, `docs/DESIGN.md`, `docs/PATTERNS.md`) are protected by three mechanisms:

**Edit guard** — Only five agents may write to documentation files:

| File | Permitted writers |
|------|-------------------|
| `docs/SPEC.md` | spec-writer |
| `docs/DESIGN.md` | design-writer, refactor, doc-harmonizer |
| `docs/PATTERNS.md` | patterns-writer, refactor, doc-harmonizer |

The doc-harmonizer may only write after presenting proposed amendments to the user and receiving explicit approval. This satisfies the SPEC constraint that no documentation changes may be applied by the doc-harmonizer without user approval.

All other agents (execute, compliance, tech-researcher, and any subagents they spawn) must treat these files as read-only. This is enforced at the skill level — each non-doc agent's skill instructions explicitly state that `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` are read-only and must not be written to.

**Commit-after-write (CLI Enforced)** — Every agent that writes to a documentation file must commit that file immediately after writing. The CLI enforces this: after a session finishes, it checks if the relevant doc file is dirty and performs the commit if the agent failed to do so.

| Agent | Commits |
|-------|---------|
| spec-writer | `docs/SPEC.md` |
| design-writer | `docs/DESIGN.md` |
| patterns-writer | `docs/PATTERNS.md` |
| doc-harmonizer | whichever doc(s) it amended |
| refactor | `docs/DESIGN.md` and/or `docs/PATTERNS.md` |

The commit message follows the format `docs: update <FILENAME> via <agent-name>`. No push is performed — the commit is local only.

**Follow-up Triggers (CLI Enforced)** — The CLI automatically launches follow-up agents after a session completes successfully:

- After `spec`, `design`, or `patterns`: Launches `doc-harmonizer` to detect cross-doc conflicts.
- After `design`: Launches `tech-researcher` to refresh project reference skills.
- After `execute`: Launches `compliance-checker` to verify implementation against docs.

### Session Lifecycle

Every assistant session launched via the CLI (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) follows a managed lifecycle in `cli.py`:

1. **Pre-session guards** — Record `SPEC.md` hash (to detect unauthorized writes).
2. **Resolve and Launch** — Resolve the preferred agent and model, sync skills, and launch the assistant subprocess.
3. **Enforce Commit** — After successful exit (RC=0), check if the relevant doc file is dirty. If so, stage and commit it with a standardized message.
4. **Trigger Follow-ups** — Launch the appropriate follow-up agents (harmonizer, researcher, compliance) as separate sessions. After design sessions, the tech-researcher trigger uses heading-level section hashing (see Tech Research Contract) rather than unconditional launch.
5. **Post-session guards** — Compare `SPEC.md` hash and warn if it was modified outside of `prothon spec`.

**Content constraints** — In addition to edit permissions, PATTERNS.md has content form rules (R25-R26):

- The patterns-writer skill guards must refuse implementation logic in code blocks and limit code examples to function and method signatures (name, parameter types, and return types) only.
- The compliance checker includes doc-form verification as part of its SPEC compliance pass, checking PATTERNS.md code blocks against R25-R26 and reporting violations as FAIL rows.
- No runtime enforcement is needed — these are authored content constraints enforced at write-time (patterns-writer guards) and audit-time (compliance checker).

### Tech Research Contract

The tech-researcher generates reference skills in .agents/skills/ based on the technology choices in DESIGN.md (serves R43-46). It runs as a post-write quality gate after any agent modifies DESIGN.md, but only when technology choices have materially changed.

**Trigger condition** — After a session that modifies DESIGN.md, the CLI compares the Technology Choices and Key Decisions sections before and after the session. If the content differs, the tech-researcher is launched. Section extraction uses heading-level parsing (`##` and `###` markers), not LLM judgment. Changes limited to other sections (Architecture, Interfaces, contracts, etc.) do not trigger it.

**Mechanism** — Before launching a design session, the CLI extracts the Technology Choices and Key Decisions sections from DESIGN.md using heading-level boundaries and computes a hash of each. After the session completes, it re-extracts and re-hashes the same sections. The tech-researcher is launched only if at least one hash differs. This replaces the previous approach where the responsible agent determined the trigger by inspecting the scope of its own changes.

### Compliance Report Contract

The compliance checker reads all three documentation levels and all source code, then produces three tables (SPEC compliance, DESIGN compliance, PATTERNS compliance). Each row contains: the checkable statement, a PASS/FAIL/SKIP status, and `file:line` evidence. SKIP indicates a check was not applicable (e.g., no files declared for that category). A summary section reports overall percentage and prioritized action items.

### Refactor Contract

The refactor subsystem discovers drift between documentation and code, then generates a promise file to orchestrate remediation. It operates in two waves: Wave 0 (documentation quality) and Wave 1 (code drift), each with discovery and promise generation phases.

**DriftFinding data model:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Short identifier for the finding (e.g. "Missing SPEC.md", "Large file: commands.py") |
| `rationale` | `str` | Explanation of why this finding matters and what should change |
| `category` | `DriftCategory` | Enum identifying the drift category — one of the values from the drift categories table below |
| `severity` | `Severity` | Enum for impact level: `HIGH`, `MEDIUM`, or `LOW` |
| `doc_sections` | `list[str]` | Documentation files or sections relevant to the finding (empty if code-only) |
| `files_affected` | `list[Path]` | Filesystem paths impacted by the finding (used to populate promise task file lists) |
| `evidence` | `list[str]` | Specific metrics, file:line references, or data points supporting the finding |

**Drift categories:**

The discovery phase checks six categories of drift across two waves:

| Wave | Category | What it detects | Example finding |
|------|----------|----------------|-----------------|
| 0 | `design_quality` | Design decisions that have become suboptimal as the project grew — decision interactions, outgrown module boundaries, missing abstractions, stale technology choices | "commands.py hub pattern has outgrown flat-module design" |
| 0 | `pattern_quality` | Patterns that could be improved holistically — uncodified recurring patterns, inconsistently applicable conventions, over-specific patterns, cross-module logic duplication | "File I/O guard pattern used in 6 modules but not codified" |
| 1 | `doc_hierarchy` | Missing core documentation files in the SPEC → DESIGN → PATTERNS chain | "Missing PATTERNS.md" when DESIGN.md exists |
| 1 | `patterns_compliance` | PATTERNS.md formatting violations detected by `check_patterns_doc()` | Code blocks containing implementation logic instead of signatures |
| 1 | `large_files` | Source files in `src/` exceeding 500 lines | "Large file: commands.py" with line count rationale |
| 1 | `missing_tests` | Source modules with testable logic that lack corresponding test files | "Missing tests for refactor.py" when no `test_refactor*.py` exists |

**Wave 0 evidence gathering:**

Wave 0 findings are LLM-driven but grounded in programmatic evidence. Three evidence-gathering functions provide structured data for the agent to reason over:

`collect_module_metrics(root: Path) -> list[ModuleMetrics]` — For each Python module under `src/`, collects: line count, public function count, import count (both inbound and outbound). Returns a list of `ModuleMetrics` dataclasses. This surfaces modules that have outgrown their design boundary or become coupling hubs.

`collect_pattern_usage(root: Path) -> list[PatternOccurrence]` — AST scan across all modules under `src/` for recurring structural patterns: try/except guards around file I/O, check-then-act conditionals, path existence checks before reads, and similar shapes. Returns occurrences grouped by pattern type. This surfaces candidates for uncodified patterns.

`collect_cross_module_similarities(root: Path) -> list[SimilarityGroup]` — Identifies public functions across different modules that share a name. Each `SimilarityGroup` entry includes the function name, file path, and parameter names, allowing consumers to further assess signature similarity. Returns entries for functions that appear in more than one file. This surfaces logic duplication candidates.

The agent receives these metrics alongside the full documentation and produces `design_quality` and `pattern_quality` findings. SPEC.md is read for context but never modified.

**Wave 0 cascade:**

After Wave 0 tasks (documentation improvements) are executed and committed, the doc-harmonizer runs automatically to ensure DESIGN↔PATTERNS consistency. Only then does Wave 1 discovery run, ensuring code-level findings reference the improved documentation rather than the original.

**Wave 1 discovery specification:**

`discover_drift(root: Path) -> list[DriftFinding]` — Scans the project at `root` and returns all findings across the four Wave 1 drift categories. Each category checker runs independently and returns zero or more findings. The function concatenates all results in category order (doc hierarchy, patterns compliance, large files, missing tests). All returned findings have their `category` field set to the corresponding category identifier and `severity` set based on the checker's assessment.

Testable logic detection uses AST analysis to skip modules containing only constants, type aliases, trivial pass-through functions, data classes without methods, and abstract/protocol classes. Test file matching supports `test_<module>.py`, `test_*_<module>.py`, and `*_<module>_test.py` naming conventions.

**Promise generation specification:**

`generate_refactor_promise(root: Path, findings: list[DriftFinding]) -> Promise` — Converts selected findings into a Promise object suitable for writing to `docs/change_promise.toml`. Each finding maps to exactly one task. The mapping is:

| DriftFinding field | Task field |
|--------------------|------------|
| `title` | `title` |
| `rationale` | `goal` |
| `title` (templated) | `success_criteria` ("Resolve the drift identified: {title}") |
| `files_affected` (existing) | `files_to_modify` |
| `files_affected` (non-existing) | `files_to_create` |
| `doc_sections` | `doc_sections` |

The promise metadata captures `base_commit` (current HEAD SHA) and `created_at` (ISO 8601 UTC timestamp). Tasks are ordered by the refactor wave principle: DESIGN-level findings first, then PATTERNS-level, then CODE-level. This ensures documentation is updated before code changes that depend on it.

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
3. Creates `docs/` directory with scaffolds for SPEC.md, DESIGN.md, and PATTERNS.md. For existing projects, the command must use static analysis (AST) to intelligently pre-populate PATTERNS.md with discovered code signatures and conventions, satisfying the "signature-only" constraint (R25-R26).
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
| Gemini CLI | `~/.gemini/skills/` |

Symlinks point directly from the backend's skill directory to the bundled package directory. Each backend maintains its own set of symlinks (no shared central location). The duplication cost is zero since symlinks have no disk footprint.

Project-specific reference skills generated by the tech-researcher live in each project's `.agents/skills/` directory. Claude Code, opencode, and Gemini CLI discover `.agents/skills/` natively, so no backend-specific handling is needed for project skills.

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
| Task quality gate | `pre-commit run --all-files` | `uv run poe check` | Mandatory project-wide health check (lint, type, test, etc.) run after every task implementation. Consistent with the Task Lifecycle step 4. Ensures 100% project health. Matches requirement R32. |
| Fix Mandate | **Global Health Enforcement** | Surgical updates only | Agent must fix all errors/warnings project-wide (including pre-existing) before a task is verified. Prevents accumulation of tech debt. |
| Templating engine | Copier | Cookiecutter, custom Jinja2 | Template updating (`copier update` with 3-way merge) is the decisive factor. Neither alternative provides it. Clean Python API for library embedding. |
| TOML library | tomlkit | tomllib + tomli-w, toml (uiri) | Comment/formatting preservation on roundtrip is essential for human-authored promise files. Single library for read and write. Maintained by Poetry organization. |
| Git interaction | subprocess wrapper | GitPython, pygit2, dulwich | All operations are single CLI commands with machine-readable flags. `--numstat` is trivial via subprocess but problematic with dulwich. Zero dependencies. GitPython is in maintenance mode with multiple SEALs. |
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
| Retry configuration | Project default in `[tool.prothon].max_attempts` + per-task override in promise TOML | CLI flag; env var; promise metadata section | Two-level resolution (project + per-task) follows existing config patterns. Retry count doesn't warrant CLI flag or env var precedence levels. Per-task override lets the planning agent adjust for task complexity. |
| Retry enforcement | Skill prompt reads `max_attempts` from promise file | Programmatic `attempt_task()` with file locking; hybrid skill + validation | Skill prompt already manages the retry loop. Reading `max_attempts` from the promise file is the minimal change. Programmatic enforcement can be added later if stricter guarantees are needed. |
| PATTERNS.md content form | Signature-only code, natural language rationale | Allow full code examples; no code at all | Signatures communicate interface contracts without prescribing implementation. Full code examples drift from actual implementations and constrain developer judgment. No code at all loses the precision of typed signatures. |
| Documentation content contracts | Explicit section structure and content rules for all three doc levels | Implicit via skill instructions only; single combined contract | Each doc level has distinct content rules (SPEC: no tech choices; DESIGN: no code; PATTERNS: no implementation logic). Explicit contracts make the hierarchy self-describing and enable compliance checking. Per-level contracts are clearer than a single combined contract. |
| Compliance Evidence Strategy | Hybrid (Regex, AST, LLM) | Pure LLM; Pure Static | Balances speed and precision with semantic understanding. |
| Refactor Orchestration | 3-layer Wave (DESIGN -> PATTERNS -> CODE) | Code-first refactor | Maintains documentation as the source of truth for architectural shifts and proactive optimization. |
| Harmonization Mechanism | Semantic LLM Cross-Referencing | Keyword matching; manual audit | Essential for natural language documentation consistency. |
| Tech-Researcher Sourcing | uv + Direct Web Fetch | Context7/MCP; Training data only | Version accuracy and cost efficiency without usage limits. |
| Tech-Researcher Structure | Three-level Progressive Disclosure (`SKILL.md` + `references/`) | Single large `SKILL.md` | Follows Anthropic best practices for context efficiency. Level 1 discovery via frontmatter, Level 2 core instructions, Level 3 deep references. |
| Adoption Strategy | AST Pattern Miner + Idiom Matcher | Empty scaffold; LLM-based discovery | AST Miner is fast, local, and zero-cost while pre-populating PATTERNS.md with compliant signatures (R25-R26). |
| Mutation Testing CI | Non-blocking Asynchronous Audit | Blocking CI gate | Provides feedback without impeding development speed. |
