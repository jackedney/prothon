# Interface Contracts

Detailed behavioral contracts for prothon's subsystems. Summaries live in `DESIGN.md → Interfaces`; this file provides the full specifications.

## Promise Contract Format

`docs/change_promise.toml` — the contract between the planning phase and execution phase of `prothon execute`.

```toml
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

## Promise Verification Contract

Each task verification produces a `TaskCheckReport` containing a list of `CheckResult` entries. Each `CheckResult` has a `CheckStatus` enum (imported from `compliance.py`; members: `PASS`, `FAIL`, `SKIP`), a summary string, and a list of `FileCheckDetail` records providing per-file granularity (path, expected state, actual state, status). `CheckStatus` is defined canonically in `compliance.py` and shared across both promise verification and compliance checking to avoid duplicate definitions. SKIP indicates a check was not applicable (e.g. no files declared for that category). A report passes if it contains no FAIL entries — SKIP results do not affect the outcome.

Dependency resolution uses `task_id` lookup: each entry in a task's `dependencies` list is matched against the `task_id` field of other tasks in the promise file, not against positional indices. This ensures dependencies remain valid when tasks are reordered, inserted, or removed during planning.

Tolerance for line counts: +-30% or +-30 lines, whichever is greater. Binary files are excluded from line counts.

**Flexible Scope:** Verification allows the agent to modify files not explicitly declared in the task's `files_to_modify` if those changes are necessary to satisfy the quality gate (R32). This is a deliberate extension of R31's strict plan-verification scope — R32 requires that pre-commit hooks pass after each task, which may necessitate fixes to files outside the task's declared scope (e.g., linting fixes in imports, formatting in adjacent code). This serves requirements 27-33 (execution verification) and 34-37 (compliance verification).

## Assistant Backend Contract

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

Canonical-to-backend subagent type mapping:

| Canonical name | Claude Code | opencode | Gemini CLI |
|---------------|-------------|----------|------------|
| `general-purpose` | `general-purpose` | `general` | `generalist_agent` |
| `explore` | `Explore` | `explore` | `codebase_investigator` |
| `plan` | `Plan` | `plan` | `generalist_agent` |

A shared launch lifecycle handles: binary existence check (via `shutil.which()`), skill syncing, environment merging (`os.environ` + `env_overrides()`), subprocess execution, and return code reporting. When the binary is missing, the error message includes the backend's `install_hint`.

A `register_backend(name, cls)` function allows programmatic extension for testing or embedding. Entry points are not used — there are no third-party consumers, and adding entry point discovery later is a trivial change.

## Agent Configuration Contract

The user selects their preferred agent via a 5-level precedence chain. The first non-empty value wins:

| Priority | Source | Mechanism | Example |
|----------|--------|-----------|---------|
| 1 (highest) | CLI flag | `--agent` / `-a` per-command option | `prothon spec --agent opencode` |
| 2 | Environment variable | `PROTHON_AGENT` | `export PROTHON_AGENT=opencode` |
| 3 | Project config | `[tool.prothon]` in `pyproject.toml` | `agent = "opencode"` |
| 4 | Global config | `~/.config/prothon/config.toml` (respects `$XDG_CONFIG_HOME`) | `agent = "opencode"` |
| 5 (lowest) | Default | Hardcoded | `"claude-code"` |

Resolution is implemented as a `resolve_agent(cli_value)` function in `config.py`. Each subcommand passes its `--agent` value (which Typer resolves from CLI flag or env var) as `cli_value`. Levels 3-4 are resolved by reading TOML files with `tomlkit`.

The `--agent` option is per-command, defined on each command that launches an assistant session (`spec`, `design`, `patterns`, `execute`, `compliance`, `refactor`) via a shared `AgentOption` annotated type. Commands that don't launch a session (`new`, `init`, `promise *`) don't have the option.

Valid backend keys match the registry: `claude-code`, `opencode`, `gemini`. When an invalid key is provided, the error message lists all registered backends. When the resolved backend's binary is missing, the error message includes the backend's `install_hint`.

## Model Configuration Contract

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
- If `--model` already contains a `/` (e.g. `--model z-ai/glm-5`), it is treated as a complete `provider/model` specifier. If `--provider` is also set, prothon verifies the providers match and raises `ProthonError` on conflict (e.g. `--model z-ai/glm-5 --provider openai`). If they match, `--provider` is silently accepted.
- If only one of model or provider resolves to a value (and the model value does not contain `/`), prothon exits with an error: `--provider requires --model (and vice versa). Use provider/model format or set both.`
- If neither resolves to a value, opencode is invoked without `--model`, deferring to opencode's own configuration and defaults.
- When the resolved agent is `claude-code` or `gemini`, both options are silently ignored — these backends do not support model selection via prothon.
- Resolution is implemented as a `resolve_model(cli_model, cli_provider)` function in `config.py`.

## Documentation Safety Contract

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
- After `design`: Launches `tech-researcher` to refresh project reference skills (only when Technology Choices or Key Decisions sections changed).
- After `execute`: Launches `compliance-checker` to verify implementation against docs.

## Session Lifecycle

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

## Tech Research Contract

The tech-researcher generates reference skills in `.agents/skills/` based on the technology choices in DESIGN.md (serves R43-46). It runs as a post-write quality gate after any agent modifies DESIGN.md, but only when technology choices have materially changed.

**Trigger condition** — After a session that modifies DESIGN.md, the CLI compares the Technology Choices and Key Decisions sections before and after the session. If the content differs, the tech-researcher is launched. Section extraction uses heading-level parsing (`##` and `###` markers), not LLM judgment. Changes limited to other sections (Architecture, Interfaces, contracts, etc.) do not trigger it.

**Mechanism** — Before launching a design session, the CLI extracts the Technology Choices and Key Decisions sections from DESIGN.md using heading-level boundaries and computes a hash of each. After the session completes, it re-extracts and re-hashes the same sections. The tech-researcher is launched only if at least one hash differs.

## Compliance Report Contract

The compliance checker reads all three documentation levels and all source code, then produces three tables (SPEC compliance, DESIGN compliance, PATTERNS compliance). Each row contains: the checkable statement, a PASS/FAIL/SKIP status, and `file:line` evidence. SKIP indicates a check was not applicable (e.g., no files declared for that category). A summary section reports overall percentage and prioritized action items.

## Scaffolding Contract

`prothon new` collects six inputs (module name, description, author name, author email, Python version, license) and passes them to Copier's `run_copy()`. The template produces a complete project with: `src/` layout, `pyproject.toml`, pre-commit hooks, CI workflows, git repo with initial commit, `AGENTS.md` with agent instruction content plus symlinks (`CLAUDE.md → AGENTS.md`, `GEMINI.md → AGENTS.md`, `AGENT.md → AGENTS.md`), doc scaffolds, `.agents/skills/` directory, and version-bump CI workflows for GitHub Actions and GitLab CI/CD. A `.copier-answers.yml` file is written to enable future `copier update` calls.

The generated `pyproject.toml` includes `[tool.prothon.ci]` with `auto_version = true`.

## Adoption Contract

`prothon init` overlays the documentation-driven workflow onto an existing Python project without touching its code, configuration, or git history. It performs the following steps in order:

1. Verifies the current directory is a git repository (exits with error if not).
2. Verifies `docs/SPEC.md` does not exist (exits with error if it does, directing the user to `prothon new` or manual setup).
3. Creates `docs/` directory with scaffolds for SPEC.md, DESIGN.md, and PATTERNS.md. For existing projects, the command must use static analysis (AST) to intelligently pre-populate PATTERNS.md with discovered code signatures and conventions, satisfying the "signature-only" constraint (R25-R26).
4. Creates `AGENTS.md` at the project root with agent instruction content, plus symlinks: `CLAUDE.md → AGENTS.md`, `GEMINI.md → AGENTS.md`, `AGENT.md → AGENTS.md`.
5. Creates `.agents/skills/` directory for project-specific reference skills.
6. Adds version-bump CI workflow files (GitHub Actions and/or GitLab CI/CD) if not already present.
7. Appends `[tool.prothon.ci]` section to `pyproject.toml` with `auto_version = true` if the section does not already exist.
8. Prints a summary of all created files and suggests `prothon spec` as the next step.

The command must not modify existing source files, dependencies, toolchain configuration, pre-commit hooks, or git history. The command may add CI workflow files and append to `pyproject.toml`.

## Skill Discovery Contract

Bundled skills live in `src/prothon/skills/` as directories containing `SKILL.md`. On every CLI invocation that launches an assistant session, the active backend's `sync_skills()` method symlinks each bundled skill directory into that backend's discovery location.

Symlinks point directly from the backend's skill directory to the bundled package directory. Each backend maintains its own set of symlinks (no shared central location). The duplication cost is zero since symlinks have no disk footprint.

Project-specific reference skills generated by the tech-researcher live in each project's `.agents/skills/` directory. Claude Code, opencode, and Gemini CLI discover `.agents/skills/` natively, so no backend-specific handling is needed for project skills.

## Skill Authoring Contract

Skills that need to spawn subagents must use **canonical agent type names** from the subagent type mapping table in the Assistant Backend Contract. Skills must NOT reference tool-specific APIs. Instead, skills must use a standardized instruction format:

> Spawn a subagent (type: `general-purpose`, fresh context) with this prompt: ...

The canonical format is: `Spawn a subagent (type: <canonical-name>, fresh context) with this prompt:` followed by the prompt content. Each assistant's LLM is responsible for translating this instruction into its native tool call.

Skill frontmatter fields that are assistant-specific (`context: fork`, `model: sonnet`, `agent:`) are **Claude Code extensions** — opencode silently ignores them. Skills must not depend on these fields for correct behavior.

## Version Bumping Contract

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

## CI Workflow Contract

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

## Refactor Contract

The refactor subsystem discovers drift between documentation and code, then generates a promise file to orchestrate remediation. It operates in two waves: Wave 0 (documentation quality) and Wave 1 (code drift), each with discovery and promise generation phases.

**DriftFinding data model:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Short identifier for the finding |
| `rationale` | `str` | Explanation of why this finding matters |
| `category` | `DriftCategory` | Enum identifying the drift category |
| `severity` | `Severity` | Enum for impact level: `HIGH`, `MEDIUM`, or `LOW` |
| `doc_sections` | `list[str]` | Documentation files or sections relevant to the finding |
| `files_affected` | `list[Path]` | Filesystem paths impacted by the finding |
| `evidence` | `list[str]` | Metrics, file:line references, or data points |

**Drift categories:**

The discovery phase checks six categories of drift across two waves:

| Wave | Category | What it detects | Example finding |
|------|----------|----------------|-----------------|
| 0 | `design_quality` | Design decisions that have become suboptimal | "commands.py hub pattern has outgrown flat-module design" |
| 0 | `pattern_quality` | Patterns that could be improved holistically | "File I/O guard pattern used in 6 modules but not codified" |
| 1 | `doc_hierarchy` | Missing core documentation files | "Missing PATTERNS.md" when DESIGN.md exists |
| 1 | `patterns_compliance` | PATTERNS.md formatting violations | Code blocks containing implementation logic |
| 1 | `large_files` | Source files in `src/` exceeding 500 lines | "Large file: commands.py" |
| 1 | `missing_tests` | Source modules with testable logic lacking tests | "Missing tests for refactor.discovery" |

**Wave 0 evidence gathering:**

Wave 0 findings are LLM-driven but grounded in programmatic evidence. Three evidence-gathering functions provide structured data:

- `collect_module_metrics(root)` — For each Python module under `src/`, collects: line count, public function count, import count. Surfaces modules that have outgrown their design boundary.
- `collect_pattern_usage(root)` — AST scan for recurring structural patterns (`TRY_EXCEPT_FILE_IO`, `PATH_EXISTS_GUARD`). Surfaces candidates for uncodified patterns.
- `collect_cross_module_similarities(root)` — Identifies public functions across different modules that share a name. Surfaces logic duplication candidates.

**Wave 0 cascade:**

After Wave 0 tasks are executed and committed, the doc-harmonizer runs automatically to ensure DESIGN↔PATTERNS consistency. Only then does Wave 1 discovery run.

**Promise generation:**

`generate_refactor_promise(root, findings)` converts selected findings into a Promise object. Each finding maps to exactly one task:

| DriftFinding field | Task field |
|--------------------|------------|
| `title` | `title` |
| `rationale` | `goal` |
| `title` (templated) | `success_criteria` |
| `files_affected` (existing) | `files_to_modify` |
| `files_affected` (non-existing) | `files_to_create` |
| `doc_sections` | `doc_sections` |

Tasks are ordered by the refactor wave principle: DESIGN-level findings first, then PATTERNS-level, then CODE-level.

## Doc-Harmonizer (R24)

The doc-harmonizer maintains internal consistency across the documentation hierarchy.

- **Semantic Cross-Referencing:** Uses LLM-based analysis to detect contradictions and scope creep (e.g., DESIGN introducing requirements that belong in SPEC).
- **Top-Down Enforcement:** Validates that lower-authority documents do not contradict higher-authority ones.
- **Approval Workflow:** Presents proposed amendments as "Before/After" diffs for user approval before applying changes.

## Adoption Intelligence (R13)

During `prothon init`, the system uses Python's `ast` module to scan for high-signal structural elements in existing code, pre-populating `PATTERNS.md` with existing conventions.

- **AST Pattern Miner:** Scans for high-signal structural elements (base classes, protocols, common decorators).
- **Idiom Matcher:** Pre-defined signatures for popular libraries (FastAPI, Typer, Pydantic).
- **Signature-Only Extraction:** Uses `ast.unparse()` on discovered nodes after clearing their implementation bodies (R25-R26).
- **Local Execution:** Runs entirely offline and locally during the adoption workflow.

## Mutation Testing CI (R6)

Mutation testing is integrated as an asynchronous, non-blocking audit.

- **Non-blocking Job:** Configured with `continue-on-error: true` (GitHub) or `allow_failure: true` (GitLab).
- **Artifacts:** Produces `mutants/mutmut-stats.json` for analysis.

## Retry Configuration (R33)

The `max_attempts` value is resolved via a three-level precedence:

| Priority | Source | Mechanism |
|----------|--------|-----------|
| 1 (highest) | Per-task override | `max_attempts` field in `[[tasks]]` section of `change_promise.toml` |
| 2 | Project default | `[tool.prothon].max_attempts` in `pyproject.toml` |
| 3 (lowest) | Hardcoded default | `3` |

When the executor creates the promise file, it reads `[tool.prothon].max_attempts` and sets it as the default for each task. The planning agent can override `max_attempts` on specific tasks.

Retry enforcement operates at two levels:

1. **Skill-prompt compliance** — the subagent reads `max_attempts` from the promise file and bounds its retry loop accordingly.
2. **Programmatic backstop** — `record_attempt()` must refuse to increment when `attempts >= max_attempts`, raising a `MaxAttemptsExceeded` error. This provides a programmatic backstop independent of skill-prompt compliance.

## Concurrency

Because independent tasks can run in parallel (per requirements 28 and 30), `complete_task()` uses platform-specific exclusive file locking on a sibling `.toml.lock` file to prevent lost updates when concurrent subagents mark tasks complete simultaneously. The lock covers the load → modify → save cycle so no completion is overwritten.

## Content Contracts

### SPEC.md Content Contract

SPEC.md is the highest-authority document. It defines *what* the system must do without prescribing *how*. Expected sections:

- **Purpose** — What the tool does and why it exists.
- **Requirements** — Grouped by subsystem, numbered (R1, R2, ...) using "must" language. Testable and verifiable.
- **Constraints** — Hard limits that are non-negotiable.
- **Out of Scope** — Explicitly excluded features with optional future notes.

Content rules:
- No technology choices — those belong in DESIGN.md.
- No architecture or component structure — those belong in DESIGN.md.
- No code patterns or conventions — those belong in PATTERNS.md.
- Requirements must be self-contained.

### DESIGN.md Content Contract

DESIGN.md defines *how* the system is built — architecture, technology choices, and interfaces. Expected sections:

- **Architecture** — Component structure, module layout, how components connect.
- **Technology Choices** — Table format with rationale.
- **Interfaces** — API boundaries, data formats, contracts.
- **Key Decisions** — Decision | Choice | Rationale.

Content rules:
- No code snippets — those belong in PATTERNS.md.
- No design patterns — those belong in PATTERNS.md.
- Everything must trace back to a SPEC requirement.
- Nothing may contradict SPEC.md.

### PATTERNS.md Content Contract

PATTERNS.md defines code patterns, conventions, and testing approaches. Constrained by R25-R26:

- **Natural language first** — Pattern rationale in prose, not code.
- **Signature-only code examples** — Name, parameter types, return type only.
- **Design pattern focus** — Patterns suitable for achieving DESIGN.md architecture.

Allowed: prose describing pattern trade-offs, signature examples, comparison tables.
Forbidden: full function bodies, import blocks, test implementations beyond signatures.
