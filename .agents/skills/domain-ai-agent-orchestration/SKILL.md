---
name: domain-ai-agent-orchestration
description: Domain knowledge — AI agent orchestration concepts for correct implementation
user-invocable: false
---

# AI Agent Orchestration

> Relevance: Prothon launches AI agents as subprocesses with specific skills, contexts, and constraints. Developers must understand the execution model, context boundaries, and failure modes to implement the execute workflow, agent launching, and skill management correctly.

## Core Concepts

**Agent session:** A single invocation of an AI assistant (e.g., Claude Code) with a specific skill loaded. The agent has access to the filesystem, can read/write files, and executes within the project directory. Each session is a subprocess that runs to completion or failure. Sessions are synchronous from prothon's perspective — the orchestrator waits for one to finish before starting the next.

**Skill:** A markdown file (`SKILL.md`) that provides an agent with role definition, instructions, and constraints. Skills are the mechanism for specializing a general-purpose AI assistant into a focused worker (spec-writer, compliance-checker, etc.). A skill contains:
- YAML frontmatter: name, description, model preference, context mode
- Role definition: what the agent is and what it should do
- Process steps: the workflow the agent follows
- Guards: what the agent must not do
- Output specification: what the agent produces

**Skill categories:**
- **Interactive skills** (spec-writer, design-writer, patterns-writer) — launch a conversational session where the user makes decisions
- **Automated skills** (compliance-checker, doc-harmonizer, tech-researcher) — run to completion without user interaction
- **Orchestrator skills** (execute) — coordinate multiple sub-agent sessions
- **Reference skills** (tech-*, style-*, optim-*, domain-*) — passive context loaded by agents when relevant, not directly invoked

**Skill discovery:** Agents auto-discover skills in two locations:
1. **Bundled skills** — synced from `src/prothon/skills/` to `~/.claude/skills/` (global, shared across projects)
2. **Project skills** — in `.agents/skills/` (project-local, include generated reference skills)

Bundled skills are prefixed with `prothon-` to avoid name collisions. Project skills use category prefixes (`tech-`, `style-`, `optim-`, `domain-`).

**Context isolation:** Each agent session starts fresh. It does not inherit state from previous sessions. All context must be provided through: (a) the skill content, (b) files on disk, and (c) agent instruction files (CLAUDE.md, etc.). This is why documentation is the source of truth — it persists between sessions.

**Backend abstraction:** The `AssistantBackend` Protocol (using `typing.Protocol`) defines how to invoke an AI assistant. Implementations satisfy the protocol structurally — no explicit inheritance required. Each backend (currently only Claude Code) encapsulates: binary name, CLI flags, skill installation path, and command construction. This allows adding new assistants without changing orchestration logic. The contract has four members:
- `name` — human-readable name for error messages
- `cli_command` — binary name to look up on PATH
- `build_command(skill_name)` — constructs subprocess argv
- `sync_skills()` — installs/symlinks bundled skills

**Execute workflow lifecycle:**
1. Read all documentation (SPEC, DESIGN, PATTERNS)
2. Generate a promise contract with planned tasks
3. User reviews and approves the plan
4. For each task (respecting dependency order):
   a. Launch agent subprocess with task-scoped context
   b. Wait for completion
   c. Verify actual changes against declared promise
   d. Run quality checks (ruff, ty, pytest, etc.)
   e. If verification or checks fail, retry up to max attempts
   f. If all retries exhausted, report failure and stop
5. Report overall execution status

## Mental Models

**Agents are stateless workers.** Think of each agent invocation as a pure function: it reads inputs (docs, code, skill), performs work (writes files, updates docs), and exits. There is no shared memory, no session continuity, no conversation history between invocations.

**Skills are job descriptions, not scripts.** A skill tells the agent what role to play and what constraints to follow. It does not contain step-by-step instructions that the agent executes mechanically. The agent uses judgment within the skill's boundaries.

**The execute workflow is a task queue with verification.** The orchestrator reads the promise contract, dispatches tasks to agent subprocesses sequentially (respecting dependency order), and verifies each task's output before proceeding. Failed tasks are retried up to a limit. This is analogous to a CI pipeline where each stage must pass before the next begins.

**Skill sync is an installation step, not a runtime step.** Skills are symlinked into the assistant's discovery directory before launching. They do not change during a session. If skills need updating, the session must be restarted.

**Context scoping is a quality lever.** The promise contract's `context_files` and `reference_skills` fields exist to limit what each task's agent sees. A narrow context helps the agent focus. A broad context helps the agent understand cross-cutting concerns. The planning phase must balance these.

## Edge Cases & Gotchas

- **Agent sessions can fail silently.** An agent might exit with code 0 but not have completed its task. The promise verification step catches this by checking actual file changes against declared intent. Never assume success from exit code alone.
- **Concurrent agent sessions are not safe.** Two agents writing to the same file cause race conditions. The execute workflow runs tasks sequentially for this reason. Parallelism is only safe when tasks operate on disjoint file sets.
- **Skill symlinks can go stale.** If the package is upgraded or reinstalled, existing symlinks may point to deleted paths. `sync_skills()` must handle broken symlinks by removing and recreating them.
- **Agent instruction files have a loading order.** Claude Code loads `CLAUDE.md` from the project root, then from `~/.claude/`. Project-level instructions override user-level. Prothon relies on this to set project-specific workflow rules.
- **Large context degrades agent quality.** Loading too many files or skills into a single session reduces the agent's ability to focus. The promise contract's `context_files` and `reference_skills` fields exist to scope each task's context to only what is relevant.
- **Binary not found is a common failure mode.** Users may not have Claude Code installed, or it may not be on PATH. The backend must check for the binary before attempting to launch and provide a clear installation message.
- **Keyboard interrupt during agent session.** The subprocess should be allowed to handle its own cleanup (saving state, rolling back partial changes). Do not send SIGKILL immediately — let the interrupt propagate naturally.
- **Skill name collisions.** If a project skill has the same name as a bundled skill, behavior is undefined. The `prothon-` prefix on bundled skills and category prefixes on project skills exist to prevent this.
- **Template vs runtime skill generation.** Bundled skills are static (ship with the package). Reference skills are generated per-project by the tech-researcher. The generation must not overwrite bundled skills or create skills in the bundled directory.

## Validation Rules

- Every bundled skill directory must contain a `SKILL.md` file.
- `sync_skills()` must be idempotent — running it twice produces the same result.
- After `sync_skills()`, every bundled skill must be reachable from the assistant's discovery location.
- Agent launch must fail with `AssistantNotFoundError` if the binary is not on PATH.
- The execute workflow must not proceed to task N+1 until task N is verified (dependency ordering).
- Task retry count must never exceed the configured maximum.
- All agent-writable paths must be within the project directory (no writes to system paths).
- Bundled skills must use the `prothon-` prefix. Project skills must not use this prefix.
- Reference skills must set `user-invocable: false` in their frontmatter.
- The orchestrator must pass the project root as `cwd` to every agent subprocess.
