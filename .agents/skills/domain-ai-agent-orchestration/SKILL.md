---
name: domain-ai-agent-orchestration
description: Domain knowledge -- AI agent orchestration concepts for correct implementation
user-invocable: false
---

# AI Agent Orchestration

> Relevance: Prothon launches AI agents as subprocesses with specific skills, contexts, and constraints. Developers must understand the execution model, context boundaries, and failure modes to implement the execute workflow, agent launching, and skill management correctly.

## Core Concepts

**Agent session:** A single invocation of an AI assistant (e.g., Claude Code) with a specific skill loaded. The agent has filesystem access and executes within the project directory. Sessions are synchronous -- the orchestrator waits for completion before starting the next.

**Skill:** A markdown file (`SKILL.md`) providing an agent with role definition, instructions, and constraints. Contains:
- YAML frontmatter: name, description, model preference, context mode
- Role definition: what the agent is and should do
- Process steps: the workflow the agent follows
- Guards: what the agent must not do
- Output specification: what the agent produces

**Skill categories:**
- **Interactive** (spec-writer, design-writer, patterns-writer) -- conversational sessions where the user makes decisions
- **Automated** (compliance-checker, doc-harmonizer, tech-researcher) -- run to completion without user interaction
- **Orchestrator** (execute) -- coordinates multiple sub-agent sessions
- **Reference** (tech-*, style-*, optim-*, domain-*) -- passive context loaded by agents when relevant, not directly invoked

**Skill discovery:** Agents auto-discover skills in two locations:
1. **Bundled skills** -- synced from `src/prothon/skills/` to `~/.claude/skills/` (global)
2. **Project skills** -- in `.agents/skills/` (project-local, includes generated reference skills)

Bundled skills use `prothon-` prefix. Project skills use category prefixes (`tech-`, `style-`, `optim-`, `domain-`).

**Context isolation:** Each agent session starts fresh with no inherited state from previous sessions. All context comes through: (a) the skill content, (b) files on disk, (c) agent instruction files. This is why documentation is the source of truth -- it persists between sessions.

**Backend abstraction:** The `AssistantBackend` uses `typing.Protocol` for structural typing. Each backend encapsulates: binary name, CLI flags, skill installation path, and command construction. The contract has four members:
- `name` -- human-readable name for error messages
- `cli_command` -- binary name to look up on PATH
- `build_command(skill_name)` -- constructs subprocess argv
- `sync_skills()` -- installs/symlinks bundled skills

## Mental Models

**Agents are stateless workers.** Each invocation is a pure function: reads inputs (docs, code, skill), performs work (writes files), and exits. No shared memory or conversation history between invocations.

**Skills are job descriptions, not scripts.** A skill defines role and constraints. The agent uses judgment within those boundaries.

**Execute workflow is a verified task queue.** The orchestrator dispatches tasks sequentially (respecting dependency order), verifies each task's output before proceeding. Analogous to a CI pipeline where each stage must pass.

**Skill sync is installation, not runtime.** Skills are symlinked before launching. They do not change during a session.

**Context scoping is a quality lever.** The promise contract's `context_files` and `reference_skills` fields limit what each task's agent sees. Narrow context aids focus; broad context aids cross-cutting understanding.

## Edge Cases & Gotchas

- **Agent sessions can fail silently.** Exit code 0 does not guarantee task completion. Promise verification catches this by checking actual file changes against declared intent.
- **Concurrent sessions are unsafe.** Two agents writing to the same file cause race conditions. The execute workflow runs tasks sequentially.
- **Skill symlinks can go stale.** Package upgrades may leave broken symlinks. `sync_skills()` must handle broken symlinks by removing and recreating them.
- **Agent instruction loading order.** Claude Code loads `CLAUDE.md` from the project root, then from `~/.claude/`. Project-level instructions override user-level.
- **Large context degrades quality.** Loading too many files or skills into a single session reduces focus. The promise contract's context fields exist to scope each task.
- **Binary not found is common.** Users may not have Claude Code installed. The backend must check for the binary before launching and provide a clear installation message.
- **Keyboard interrupt during session.** Let the subprocess handle its own cleanup. Do not send SIGKILL immediately.
- **Template vs runtime skill generation.** Bundled skills are static. Reference skills are generated per-project. Generation must not overwrite bundled skills.

## Validation Rules

- Every bundled skill directory must contain a `SKILL.md` file.
- `sync_skills()` must be idempotent -- running it twice produces the same result.
- Agent launch must fail with `AssistantNotFoundError` if the binary is not on PATH.
- The execute workflow must not proceed to task N+1 until task N is verified.
- Task retry count must never exceed the configured maximum.
- Bundled skills must use the `prothon-` prefix. Project skills must not.
- Reference skills must set `user-invocable: false` in frontmatter.
- The orchestrator must pass the project root as `cwd` to every agent subprocess.
