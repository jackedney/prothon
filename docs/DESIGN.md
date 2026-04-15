# Design Document

## Architecture

> Flat module layout with two subpackages. Covers: module structure, refactor waves, assistant abstraction, and compliance checking.

### Module Structure

Mostly flat module layout under `src/prothon/`, with two subpackages (`checks/` and `refactor/`) grouping related functionality. CLI definitions and logic are distributed across dedicated modules for commands, UI, and configuration.

- `adoption.py` — Project adoption: overlaying docs-first workflow onto existing projects
- `adoption_templates.py` — Template file loading for project adoption (CI workflows, doc scaffolds)
- `ast_miner.py` — AST pattern mining and library idiom recognition (FastAPI, Typer, Pydantic)
- `assistant.py` — Backend registry, data-driven `BackendConfig`, and launch lifecycle for AI assistants
- `cli.py` — Typer app, factory-generated command definitions
- `commands.py` — Session orchestration: Skill enum, SKILL_DOC_MAP, launch lifecycle, promise subcommand handlers
- `ui.py` — Rich-based terminal UI, tables, and status reporting
- `config.py` — Multi-level configuration resolution (CLI, env, toml); imports `xdg_config_home` from `fs.py`
- `checks/` — Static compliance checks subpackage (`__init__.py` re-exports; `utils.py`, `docs.py`, `structure.py`, `workflows.py`, `research.py`, `adoption.py`)
- `compliance.py` — Compliance data types (`CheckResult`, `CheckStatus`, `ComplianceReport`)
- `exceptions.py` — Custom exception hierarchy
- `fs.py` — Shared filesystem utilities (`atomic_write`, `create_agent_symlinks`, `xdg_config_home`)
- `git.py` — Thin typed wrapper around git CLI via subprocess
- `models.py` — Shared data models (`Task`, `Metadata`, `Promise`)
- `promise.py` — Promise TOML I/O and lifecycle management
- `promise_verify.py` — Git diff analysis and task verification logic
- `project.py` — Project root detection, shared project context
- `refactor/` — Drift discovery and refactor promise generation subpackage (`models.py`, `metrics.py`, `discovery.py`, `testability.py`, `promise_gen.py`)
- `scaffold.py` — Template rendering, copier answers
- `scaffold_cli.py` — Scaffolding-specific CLI commands
- `skills.py` — Skill discovery, symlink management
- `versioning.py` — Semantic version detection, bumping, git tagging, CI orchestration
- `skills/` — Bundled skill assets (non-Python), with `_shared/` guards and per-skill directories
- `data/` — Bundled runtime assets loaded by `adoption_templates.py` (CI workflow YAMLs, `agents.md`)

Two non-Python asset directories are bundled: `skills/` and `data/` (both under `src/prothon/`, included automatically as part of the package). The project-root `template/` directory is a separate Copier project template for `prothon new`, included via `[tool.hatch.build.targets.wheel.force-include]`.

Inter-module dependency graph: see `docs/references/module-dependencies.md`.

### Task Lifecycle (R27-33)

> 7-step lifecycle with retry backstop. Only relevant if working on execute workflow.

Each task in the execute workflow follows a 7-step lifecycle: dependency check -> read context -> implement -> quality gate (`pre-commit run --all-files`) -> commit -> plan verification (`check_task()`) -> completion. Failed quality gates or verification trigger retries up to `max_attempts`, with `MaxAttemptsExceeded` as a programmatic backstop. See `docs/references/task-lifecycle.md` for the full lifecycle contract and `docs/references/contracts.md` -> Retry Configuration for precedence rules.

### Refactor Wave Logic (R38-42)

> Three-layer wavefront (DESIGN -> PATTERNS -> CODE) with programmatic evidence gathering. Only relevant if working on refactor functionality.

The Refactor Workflow is a specialized orchestrator that follows a three-layer wavefront: **DESIGN -> PATTERNS -> CODE**. Architectural shifts must be documented before code is modified.

- **Wave 0 (Documentation Quality):** Evaluates if `DESIGN.md` and `PATTERNS.md` are still optimal. Uses programmatic evidence (module metrics, pattern usage, similarity detection) to fuel LLM-driven analysis. Findings in `design_quality` and `pattern_quality` categories produce documentation updates.
- **Wave 1 (Code Drift):** Discovers gaps between source code and the (updated) documentation. Categories include `doc_hierarchy`, `patterns_compliance`, `large_files`, and `missing_tests`.
- **Execution:** Orchestrates implementation tasks using self-correcting subagent loops. Every task references the specific documentation heading or requirement it aligns with (R42).

See `docs/references/contracts.md` -> Refactor Contract for the DriftFinding data model, drift categories, Wave 0 evidence gathering, and promise generation mapping.

### Assistant Abstraction (R56-61)

> Pluggable backend system for Claude Code, opencode, and Gemini CLI. Only relevant if working on assistant integration.

A pluggable backend system enables identical behavior across supported AI assistants. Backends are defined as data-driven `BackendConfig` declarations -- each backend is a config record (name, CLI command, install hint, skill sync target, subagent type map, prompt builder) rather than a full class hierarchy. A shared `launch()` lifecycle handles binary detection, skill syncing, and subprocess execution.

AI coding CLIs fall into two structural categories:
- **Category A (native skill directories):** Claude Code, opencode, and Gemini CLI. Prothon symlinks bundled skills into each assistant's native skill directory and invokes them by name.
- **Category B (prompt injection):** Injects skill content directly into the prompt. No backends currently use this category.

See `docs/references/contracts.md` -> Assistant Backend Contract for the 7-member protocol, command construction details, subagent type mapping, and extension hook.

### Compliance Checker (R34-37)

> Hybrid AST + LLM evidence strategy producing tri-state reports. Only relevant if working on compliance verification.

The compliance checker uses a **Hybrid Evidence Strategy** to verify that code matches documentation:
- **Static Analysis (AST):** Deterministic checks for structural rules, such as the "signature-only" constraint in `PATTERNS.md` (R25-R26). Uses `ast.parse` to ensure no implementation logic exists in code blocks.
- **Semantic Analysis (LLM):** Targeted subagents verify high-level requirements that cannot be proven through static analysis.
- **Evidence Mapping:** Produces a `CheckResult` with a tri-state status (PASS, FAIL, SKIP) and `file:line` evidence.

See `docs/references/contracts.md` -> Compliance Report Contract for report format details.

### Doc-Harmonizer (R24)

The doc-harmonizer maintains internal consistency across the documentation hierarchy using semantic cross-referencing, top-down enforcement, and an approval workflow (user must approve amendments). See `docs/references/contracts.md` -> Doc-Harmonizer.

### Tech-Researcher (R43-46)

The tech-researcher generates reference skills based on technology choices in DESIGN.md. It uses a progressive disclosure structure (Level 1 frontmatter -> Level 2 SKILL.md body -> Level 3 references/). Triggered automatically when Technology Choices or Key Decisions sections change. See `docs/references/contracts.md` -> Tech Research Contract for trigger mechanism.

### Adoption Intelligence (R13)

During `prothon init`, an AST Pattern Miner with an Idiom Matcher (FastAPI, Typer, Pydantic) scans existing code to pre-populate PATTERNS.md with signature-only conventions. Runs entirely offline. See `docs/references/contracts.md` -> Adoption Intelligence.

## Technology Choices

> Six core dependencies. Consult this table when adding or changing a dependency.

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint inference | R56: CLI-invocable workflows | click, argparse |
| uv (>=0.1) | Package management and environment isolation | R4: fixed dev toolchain | pip, poetry |
| copier (>=9.0) | Project templating with `copier update` support | R1-R17: scaffolding/adoption | cookiecutter |
| tomlkit (>=0.13) | TOML read/write with formatting preservation | R27-R28: change promise contract | tomllib+tomli-w |
| rich | Table rendering for reports and status | R35: compliance report status | tabulate |
| jinja2 (>=3.1) | Template rendering for adoption scaffolds | R13-R16: project adoption | string.Template |

Extended rationale: see `docs/references/tech-rationale.md`.

## Interfaces

> Protocol definitions and data contracts. Read the subsection relevant to the component you're modifying.

All commands that launch an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) accept a per-command `--agent` / `-a` option and the `PROTHON_AGENT` environment variable. When the resolved agent is `opencode`, `--model` / `-m` and `--provider` / `-p` options control which model is used. See the Agent Configuration Contract and Model Configuration Contract for the full resolution chains.

Every assistant backend satisfies the `AssistantBackend` protocol:
- `build_command(skill_name, cwd, model=None)`: Constructs subprocess argv. For Gemini CLI, this uses `--approval-mode=yolo`.
- `sync_skills()`: Symlinks bundled skills (e.g., `~/.gemini/skills/`).
- `subagent_type_map()`: Translates canonical types (e.g., `explore`) to backend names (e.g., `codebase_investigator`).

### Assistant Backend Contract (R57, R61)

Every assistant backend satisfies the `AssistantBackend` protocol (defined in `assistant.py`). Backends are data-driven via `BackendConfig`:

| Key | Assistant | Binary | Skill Sync Target |
|-----|-----------|--------|-------------------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` |
| `gemini` | Gemini CLI | `gemini` | `~/.gemini/skills/` |

Full protocol (7 members), command construction details, and subagent type mapping: see `docs/references/contracts.md` -> Assistant Backend Contract.

### Agent Configuration Contract (R58)

Agent selection via 5-level precedence chain (CLI flag > env var > pyproject.toml > global config > default). See `docs/references/contracts.md` -> Agent Configuration Contract for the full table with examples.

### Model Configuration Contract (R61)

For `opencode`, model and provider are resolved via separate 5-level precedence chains and joined as `provider/model`. Resolution rules: slash in model value = complete specifier; only one resolved = error; neither resolved = defer to opencode defaults; non-opencode backends silently ignore. See `docs/references/contracts.md` -> Model Configuration Contract.

### Promise Contract (R27-28)

`docs/change_promise.toml` -- the contract between planning and execution phases. See `docs/references/contracts.md` -> Promise Contract Format for the full TOML schema.

### Promise Verification Contract (R31)

Verification produces a `TaskCheckReport` with per-file `FileCheckDetail`. Tolerance: +-30% or +-30 lines, whichever is greater. Dependency resolution via `task_id` lookup (not positional indices). See `docs/references/contracts.md` -> Promise Verification Contract.

### Documentation Safety Contract (R21, R24)

Three mechanisms protect documentation: edit guards (which agents may write which docs), commit-after-write (CLI-enforced), and follow-up triggers (automatic harmonizer/researcher/compliance launches). See `docs/references/contracts.md` -> Documentation Safety Contract and Session Lifecycle.

### Scaffolding Contract (R1-R9)

`prothon new` collects 6 inputs via Copier `run_copy()`. See `docs/references/contracts.md` -> Scaffolding Contract.

### Adoption Contract (R10-R17)

`prothon init` overlays the docs-first workflow in 8 steps without modifying existing source files. See `docs/references/contracts.md` -> Adoption Contract.

### Version Bumping Contract (R47-55)

Automatic semantic versioning maps documentation changes to SemVer levels:
- **Major:** `docs/SPEC.md` changed.
- **Minor:** `docs/DESIGN.md` changed (without SPEC).
- **Patch:** `docs/PATTERNS.md` or source code only.

Detection uses CI environment variables with a `git diff-tree` fallback. See `docs/references/contracts.md` -> Version Bumping Contract and CI Workflow Contract.

### Tech Research Contract (R43-46)

The tech-researcher generates skills using a **Progressive Disclosure** structure:
- **Level 1:** YAML frontmatter in `SKILL.md` for discovery and triggering.
- **Level 2:** Core instructions in `SKILL.md` (max 500 words).
- **Level 3:** Deep technical references in `docs/references/` directory.

Triggered by heading-level hash comparison of Technology Choices and Key Decisions sections. See `docs/references/contracts.md` -> Tech Research Contract.

### Adoption Template Contract (R13, D1)

`adoption_templates.py` loads CI workflow YAML and doc scaffold content from bundled data files in `data/` at runtime rather than maintaining inline string copies. Jinja templates for the Copier scaffold live in the project-root `template/` directory and are separate from the adoption data assets.

### Skill Discovery and Authoring (R59)

Bundled skills symlinked to per-backend discovery directories. Project skills in `.agents/skills/`. Skills use canonical subagent type names for portability. See `docs/references/contracts.md` -> Skill Discovery Contract and Skill Authoring Contract.

### Content Contracts

Each documentation level has explicit content rules:
- **SPEC.md:** Requirements only -- no tech choices, no architecture, no patterns.
- **DESIGN.md:** Architecture and interfaces only -- no code snippets, no patterns.
- **PATTERNS.md:** Patterns and conventions only -- no implementation logic in code blocks (R25-R26).

See `docs/references/contracts.md` -> Content Contracts for allowed/forbidden examples.

## Key Decisions

> Architectural trade-offs and their rationale. Reference when proposing changes that might conflict with prior decisions.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Refactor Orchestration | DESIGN -> PATTERNS -> CODE | Ensures architectural clarity before implementation; maintains docs as source of truth. |
| Compliance Evidence | Hybrid (AST + LLM) | High precision for structural rules and flexibility for semantic rules. |
| Tech Research Sourcing | `uv` + `web_fetch` | Version accuracy and up-to-date idiomatic knowledge without usage limits. |
| Skill Portability | Canonical subagent names | Single set of skills works across all backends via backend-specific mapping. |
| Doc Safety | Skill-level edit guards | Governs agent behavior at write-time; prevents unauthorized doc modification. |
| Mutation Testing CI | Non-blocking job | Provides feedback (continue-on-error) without slowing the main dev loop. |
| Retry Configuration | Two-level resolution | Project defaults with per-task overrides in `change_promise.toml`. |
| Backend Definitions | Data-driven `BackendConfig` | Each backend is a config record, not a class hierarchy. Reduces boilerplate from ~40 lines per backend to ~5. |
| CI Templates | External files loaded at runtime | Eliminates inline YAML strings; single source of truth in `data/` directory. |
| Skill Token Efficiency | Shared guards + progressive disclosure | Operational rules (staging, fresh instances) in `_shared/` referenced by all skills; output templates offloaded to `references/`. |

Full decision record with alternatives: see `docs/references/key-decisions.md`.
