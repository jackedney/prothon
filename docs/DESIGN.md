# Design Document

## Architecture

> Flat module layout with two subpackages. Covers: module structure, refactor waves, assistant abstraction, and compliance checking.

### Module Structure

Mostly flat module layout under `src/prothon/`, with two subpackages (`checks/` and `refactor/`) grouping related functionality. CLI definitions and logic are distributed across dedicated modules for commands, UI, and configuration.

```text
src/prothon/
    __init__.py
    adoption.py         # Project adoption: overlaying docs-first workflow onto existing projects
    adoption_templates.py  # Templates and scaffolds used during project adoption
    ast_miner.py        # AST pattern mining and library idiom recognition (FastAPI, Typer, Pydantic)
    assistant.py        # Backend registry, protocol, and launch lifecycle for AI assistants
    cli.py              # Typer app and command definitions
    commands.py         # Session orchestration hub: Skill enum, SKILL_DOC_MAP, launch lifecycle, promise subcommand handlers, and compliance pipeline coordination
    ui.py               # Rich-based terminal UI, tables, and status reporting
    config.py           # Multi-level configuration resolution (CLI, env, toml); imports `xdg_config_home` from `fs.py`
    fs.py               # Shared filesystem utilities (`atomic_write`, `create_agent_symlinks`, `xdg_config_home`, `file_hash`, `safe_parse_py`)
    checks/             # Static compliance checks subpackage
        __init__.py     # Re-exports all public check functions
        utils.py        # AST analysis, signature helpers, `check_path_exists`
        docs.py         # Document-related checks (R24-R26, R44)
        structure.py    # Package structure checks (R3-R5, R15)
        workflows.py    # Execute/refactor workflow checks (R27-R42)
        research.py     # Tech researcher and versioning checks (R43-R55)
        adoption.py     # Adoption intelligence check (R13)
    compliance.py       # Compliance data types (`CheckResult`, `CheckStatus`, `ComplianceReport`, `CheckType`, `Requirement`)
    exceptions.py       # Custom exception hierarchy
    git.py              # Thin typed wrapper around git CLI via subprocess
    models.py           # Shared data models (Task, Metadata, Promise)
    promise.py          # Promise TOML I/O and lifecycle management
    promise_verify.py   # Git diff analysis and task verification logic
    project.py          # Project root detection, shared project context
    refactor/              # Drift discovery and refactor promise generation subpackage
        __init__.py        # Re-exports all public functions
        models.py          # DriftCategory, Severity, PatternType, DriftFinding, ModuleMetrics, PatternOccurrence, SimilarityGroup
        metrics.py         # collect_module_metrics(), collect_pattern_usage(), etc.
        discovery.py       # discover_drift() and Wave 1 category checkers
        testability.py     # Testable logic detection heuristics (AST-based)
        promise_gen.py     # generate_refactor_promise()
    scaffold.py         # Template rendering, copier answers
    scaffold_cli.py     # Scaffolding-specific CLI commands
    skills.py           # Skill discovery, symlink management
    versioning.py       # Semantic version detection, bumping, git tagging, CI orchestration
    skills/             # Bundled skill assets (non-Python)

template/               # Bundled Copier project template (Jinja2), at project root
```

### Refactor Wave Logic (R38-42)

> Three-layer wavefront (DESIGN -> PATTERNS -> CODE) with programmatic evidence gathering. Only relevant if working on refactor functionality.

The Refactor Workflow is a specialized orchestrator that follows a three-layer wavefront: **DESIGN -> PATTERNS -> CODE**. Architectural shifts must be documented before code is modified.

- **Wave 0 (Documentation Quality):** Evaluates if `DESIGN.md` and `PATTERNS.md` are still optimal. Uses programmatic evidence (module metrics, pattern usage, similarity detection) to fuel LLM-driven analysis. Findings in `design_quality` and `pattern_quality` categories produce documentation updates.
- **Wave 1 (Code Drift):** Discovers gaps between source code and the (updated) documentation. Categories include `doc_hierarchy`, `patterns_compliance`, `large_files`, and `missing_tests`.
- **Execution:** Orchestrates implementation tasks using self-correcting subagent loops. Every task references the specific documentation heading or requirement it aligns with (R42).

### Assistant Abstraction (R56-61)

> Pluggable backend system for Claude Code, opencode, and Gemini CLI. Only relevant if working on assistant integration.

A pluggable backend system enables identical behavior across supported AI assistants. A shared `launch()` lifecycle handles binary detection, skill syncing, and subprocess execution.

AI coding CLIs fall into two structural categories:
- **Category A (native skill directories):** Claude Code, opencode, and Gemini CLI. Prothon symlinks bundled skills and invokes them by name.
- **Category B (prompt injection):** Injects skill content directly into the prompt (reserved for future backends).

### Compliance Checker (R34-37)

> Hybrid AST + LLM evidence strategy producing tri-state reports. Only relevant if working on compliance verification.

The compliance checker uses a **Hybrid Evidence Strategy** to verify that code matches documentation:
- **Static Analysis (AST):** Deterministic checks for structural rules, such as the "signature-only" constraint in `PATTERNS.md` (R25-R26). Uses `ast.parse` to ensure no implementation logic exists in code blocks.
- **Semantic Analysis (LLM):** Targeted subagents verify high-level requirements that cannot be proven through static analysis.
- **Evidence Mapping:** Produces a `CheckResult` with a tri-state status (PASS, FAIL, SKIP) and `file:line` evidence.

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

## Interfaces

> Protocol definitions and data contracts. Read the subsection relevant to the component you're modifying.

### Assistant Backend Contract (R57, R61)

Every assistant backend satisfies the `AssistantBackend` protocol:
- `build_command(skill_name, cwd, model=None)`: Constructs subprocess argv. For Gemini CLI, this uses `--approval-mode=yolo`.
- `sync_skills()`: Symlinks bundled skills (e.g., `~/.gemini/skills/`).
- `subagent_type_map()`: Translates canonical types (e.g., `explore`) to backend names (e.g., `codebase_investigator`).

| Key | Assistant | Binary | Skill Sync Target |
|-----|-----------|--------|-------------------|
| `claude-code` | Claude Code | `claude` | `~/.claude/skills/` |
| `opencode` | opencode | `opencode` | `~/.config/opencode/skills/` |
| `gemini` | Gemini CLI | `gemini` | `~/.gemini/skills/` |

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

> Architectural trade-offs and their rationale. Reference when proposing changes that might conflict with prior decisions.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Refactor Orchestration | DESIGN -> PATTERNS -> CODE | Ensures architectural clarity before implementation; maintains docs as source of truth. |
| Compliance Evidence | Hybrid (AST + LLM) | High precision for structural rules (signatures) and flexibility for semantic rules. |
| Tech Research Sourcing | `uv` + `web_fetch` | Version accuracy and up-to-date idiomatic knowledge without usage limits. |
| Skill Portability | Canonical subagent names | Single set of skills works across all backends via backend-specific mapping. |
| Doc Safety | Skill-level edit guards | Governs agent behavior at write-time; prevents unauthorized doc modification. |
| Mutation Testing CI | Non-blocking job | Provides feedback (continue-on-error) without slowing the main dev loop. |
| Retry Configuration | Two-level resolution | Project defaults with per-task overrides in `change_promise.toml`. |
