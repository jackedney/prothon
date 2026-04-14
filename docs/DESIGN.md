# Design Document

## Architecture

### Module Structure

Mostly flat module layout under `src/prothon/`, with two subpackages (`checks/` and `refactor/`) grouping related functionality. CLI definitions and logic are distributed across dedicated modules for commands, UI, and configuration.

- `adoption.py` — Project adoption: overlaying docs-first workflow onto existing projects
- `adoption_templates.py` — Template file loading for project adoption (CI workflows, doc scaffolds)
- `ast_miner.py` — AST pattern mining and library idiom recognition (FastAPI, Typer, Pydantic)
- `assistant.py` — Backend registry, data-driven `BackendConfig`, and launch lifecycle for AI assistants
- `cli.py` — Typer app, factory-generated command definitions
- `commands.py` — Session orchestration: Skill enum, SKILL_DOC_MAP, launch lifecycle, promise subcommand handlers
- `ui.py` — Rich-based terminal UI, tables, and status reporting
- `config.py` — Multi-level configuration resolution (CLI, env, toml), shared XDG helper
- `checks/` — Static compliance checks subpackage (`__init__.py` re-exports; `utils.py`, `docs.py`, `structure.py`, `workflows.py`, `research.py`, `adoption.py`)
- `compliance.py` — Compliance data types (`CheckResult`, `CheckStatus`, `ComplianceReport`)
- `exceptions.py` — Custom exception hierarchy
- `fs.py` — Shared filesystem utilities (`atomic_write`, `create_agent_symlinks`)
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
- `template/` — Bundled Copier project template (Jinja2) and CI workflow templates loaded by `adoption_templates.py`

### Refactor Wave Logic (R38-42)

The Refactor Workflow is a specialized orchestrator that follows a three-layer wavefront: **DESIGN -> PATTERNS -> CODE**. Architectural shifts must be documented before code is modified.

- **Wave 0 (Documentation Quality):** Evaluates if `DESIGN.md` and `PATTERNS.md` are still optimal. Uses programmatic evidence (module metrics, pattern usage, similarity detection) to fuel LLM-driven analysis. Findings in `design_quality` and `pattern_quality` categories produce documentation updates.
- **Wave 1 (Code Drift):** Discovers gaps between source code and the (updated) documentation. Categories include `doc_hierarchy`, `patterns_compliance`, `large_files`, and `missing_tests`.
- **Execution:** Orchestrates implementation tasks using self-correcting subagent loops. Every task references the specific documentation heading or requirement it aligns with (R42).

### Assistant Abstraction (R56-61)

A pluggable backend system enables identical behavior across supported AI assistants. Backends are defined as data-driven `BackendConfig` declarations — each backend is a config record (name, CLI command, install hint, skill sync target, subagent type map) rather than a full class hierarchy. A shared `launch()` lifecycle handles binary detection, skill syncing, and subprocess execution.

AI coding CLIs fall into two structural categories:
- **Category A (native skill directories):** Claude Code, opencode, and Gemini CLI. Prothon symlinks bundled skills into each assistant's native skill directory and invokes them by name.
- **Category B (prompt injection):** Injects skill content directly into the prompt. No backends currently use this category.

### Compliance Checker (R34-37)

The compliance checker uses a **Hybrid Evidence Strategy** to verify that code matches documentation:
- **Static Analysis (AST):** Deterministic checks for structural rules, such as the "signature-only" constraint in `PATTERNS.md` (R25-R26). Uses `ast.parse` to ensure no implementation logic exists in code blocks.
- **Semantic Analysis (LLM):** Targeted subagents verify high-level requirements that cannot be proven through static analysis.
- **Evidence Mapping:** Produces a `CheckResult` with a tri-state status (PASS, FAIL, SKIP) and `file:line` evidence.

## Technology Choices

| Package | Purpose | Serves Requirement | Alternatives Considered |
|---------|---------|-------------------|------------------------|
| typer (>=0.15) | CLI framework with type-hint inference | R56: CLI-invocable workflows | click, argparse |
| uv (>=0.1) | Package management and environment isolation | R4: fixed dev toolchain | pip, poetry |
| copier (>=9.0) | Project templating with `copier update` support | R1-R17: scaffolding/adoption | cookiecutter |
| tomlkit (>=0.13) | TOML read/write with formatting preservation | R27-R28: change promise contract | tomllib+tomli-w |
| rich | Table rendering for reports and status | R35: compliance report status | tabulate |
| jinja2 (>=3.1) | Template rendering for adoption scaffolds | R13-R16: project adoption | string.Template |

## Interfaces

### Assistant Backend Contract (R57, R61)

Every assistant backend satisfies the `AssistantBackend` protocol (defined in `assistant.py`). Backends are data-driven via `BackendConfig`:

| Key | Assistant | Binary | Skill Sync Target |
|-----|-----------|--------|-------------------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` |
| `gemini` | Gemini CLI | `gemini` | `~/.gemini/skills/` |

### Adoption Template Contract (R13, D1)

`adoption_templates.py` loads CI workflow YAML and doc scaffold content from bundled template files at runtime rather than maintaining inline string copies. The adoption path reuses the same Jinja templates and external YAML files that `template/` provides, eliminating duplicate content.

### Model Configuration Contract (R61)

For `opencode`, model and provider are resolved via a 5-level precedence chain (CLI > env > project > global > default). If both resolve, they are joined as `provider/model` for the `--model` flag.

### Version Bumping Contract (R47-55)

Automatic semantic versioning maps documentation changes to SemVer levels:
- **Major:** `docs/SPEC.md` changed.
- **Minor:** `docs/DESIGN.md` changed (without SPEC).
- **Patch:** `docs/PATTERNS.md` or source code only.

Detection uses CI environment variables (e.g., `GITHUB_SHA`) with a `git diff-tree` fallback.

### Tech Research Contract (R43-46)

The tech-researcher generates skills using a **Progressive Disclosure** structure:
- **Level 1:** YAML frontmatter in `SKILL.md` for discovery and triggering.
- **Level 2:** Core instructions in `SKILL.md` (max 500 words).
- **Level 3:** Deep technical references in `docs/references/` directory.

### Adoption Contract (R13)

`prothon init` intelligently pre-populates the documentation hierarchy. It uses the `ASTPatternMiner` to extract signature-only conventions (R25-R26) from existing code, placing them in `docs/references/modules.md` (Level 3) which is linked from the `PATTERNS.md` scaffold (Level 2).

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Refactor Orchestration | DESIGN -> PATTERNS -> CODE | Ensures architectural clarity before implementation; maintains docs as source of truth. |
| Compliance Evidence | Hybrid (AST + LLM) | High precision for structural rules (signatures) and flexibility for semantic rules. |
| Tech Research Sourcing | `uv` + `web_fetch` | Version accuracy and up-to-date idiomatic knowledge without usage limits. |
| Skill Portability | Canonical subagent names | Single set of skills works across all backends via backend-specific mapping. |
| Doc Safety | Skill-level edit guards | Governs agent behavior at write-time; prevents unauthorized doc modification. |
| Mutation Testing CI | Non-blocking job | Provides feedback (continue-on-error) without slowing the main dev loop. |
| Retry Configuration | Two-level resolution | Project defaults with per-task overrides in `change_promise.toml`. |
| Backend Definitions | Data-driven `BackendConfig` | Each backend is a config record, not a class hierarchy. Reduces boilerplate from ~40 lines per backend to ~5. |
| CI Templates | External files loaded at runtime | Eliminates inline YAML strings; single source of truth in `template/` directory. |
| Skill Token Efficiency | Shared guards + progressive disclosure | Operational rules (staging, fresh instances) in `_shared/` referenced by all skills; output templates offloaded to `references/`. |
