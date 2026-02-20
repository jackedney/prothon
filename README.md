<div align="center">

```
1 █▀▀▄ █▀▀▄ ▄▀▀▄ ▀█▀ █  █ ▄▀▀▄ █▄  █
2 █▄▄█ █▄▄▀ █  █  █  █▄▄█ █  █ █ █ █
  3 █    █  █ ▀▄▄▀  █  █  █ ▀▄▄▀ █  ▀█ ●
```

**docs-first project generator for AI-assisted Python development**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/installer-uv-blueviolet.svg)](https://docs.astral.sh/uv/)

</div>

&nbsp;

AI coding assistants drift. Early in a project the AI knows what you want, but as requirements change and sessions accumulate, it starts making assumptions — picks wrong patterns, contradicts earlier decisions, ignores constraints set weeks ago. There's no shared source of truth, so every prompt is a fresh negotiation.

prothon generates Python projects with a documentation hierarchy the AI treats as authoritative instructions, dedicated skills that guide each phase of development, and a verification loop that catches when code drifts from intent.

```
    SPEC.md  ──→  DESIGN.md  ──→  PATTERNS.md  ──→  code
  requirements    architecture     conventions      implementation
   (highest)                                         (verified)
```

---

## install

Requires [uv](https://docs.astral.sh/uv/).

```bash
# run directly (no install needed)
uvx --from "git+https://github.com/jackedney/prothon" prothon new my-project

# install globally
uv tool install "git+https://github.com/jackedney/prothon"

# pin to a specific version
uv tool install "git+https://github.com/jackedney/prothon@v0.1.0"

# one-liner (⚠ always pulls latest from master, use at your own risk)
curl -fsSL https://raw.githubusercontent.com/jackedney/prothon/master/install.sh | sh
```

## quickstart

### new project

```bash
cd my-project
uv sync
prothon spec       # define requirements   (writes SPEC.md)
prothon design     # choose architecture   (writes DESIGN.md)
prothon patterns   # set conventions       (writes PATTERNS.md)
prothon execute    # implement code from docs
```

### existing project

```bash
cd your-existing-repo
prothon init       # overlay docs-first workflow (creates docs/, AGENTS.md, symlinks)
prothon spec       # define requirements
prothon design     # choose architecture
prothon patterns   # set conventions
prothon execute    # implement code from docs
```

`prothon init` adds the documentation hierarchy and agent instruction files without touching your existing code, config, dependencies, or git history.

Each command launches a Claude Code session with the corresponding skill. The skill asks you questions, researches options, and writes the doc. You make the decisions.

Once your docs are in place, the AI has full context via `AGENTS.md` and follows the documented hierarchy for all future work. Generated projects symlink `AGENTS.md` to `CLAUDE.md`, `GEMINI.md`, and `AGENT.md` so the instructions are picked up automatically regardless of which AI coding assistant you use.

---

## how it works

### the documentation hierarchy

Three documents form a strict authority chain. Higher levels override lower ones — when things conflict, the higher document wins and lower documents get amended.

```
docs/
├── SPEC.md        # requirements & constraints        (highest authority)
├── DESIGN.md      # architecture & technology choices
└── PATTERNS.md    # code conventions & testing         (lowest authority)
```

Each document has a dedicated skill that guides you through writing it conversationally — one decision at a time, with options, trade-offs, and recommendations. The skills enforce boundaries: the spec-writer refuses to discuss technology choices, the design-writer refuses to include code snippets, and so on. Content lands in the right document or not at all.

### changes cascade top-down

When a requirement changes, SPEC.md gets updated. That may invalidate decisions in DESIGN.md, which may invalidate conventions in PATTERNS.md. The cascade enforces that you resolve conflicts before writing code.

```
requirement changes  →  prothon spec  →  prothon design  →  prothon patterns  →  implement
design changes       →                   prothon design  →  prothon patterns  →  implement
convention changes   →                                      prothon patterns  →  implement
```

### docs stay in sync with code

Three mechanisms close the loop:

- **doc-harmonizer** runs automatically after any doc is written and cross-references all three levels. If DESIGN.md contradicts SPEC.md, or PATTERNS.md assumes technology not chosen in DESIGN.md, you find out before a line of code is written.
- **compliance-checker** reads every checkable statement from the docs and verifies the code implements it, producing a table with PASS/FAIL/PARTIAL status and `file:line` evidence. This runs as an always-on quality gate — the AI is instructed to launch it before claiming any work is complete.
- **change promises** (`docs/change_promise.toml`) are a contract between planning and execution. Each task declares exactly what files it will create, modify, or remove, and the expected line counts. This forces the planner to think through what the implementation actually involves — it can't hand-wave scope. After a task completes, `prothon promise check` diffs against the base commit to verify what actually happened. If the real diff is wildly different from the prediction, either the plan was sloppy or the implementation veered off course. Discrepancies trigger retries or get escalated.

### the AI learns your stack

When you make technology choices in DESIGN.md, the **tech-researcher** fires automatically and generates reference skills — current documentation, idioms, and best practices for the specific libraries you chose. These land in `.agents/skills/` as `tech-*`, `style-*`, `optim-*`, and `domain-*` files that the AI loads during implementation. It doesn't just know your requirements; it has up-to-date reference material for your exact stack.

### execute: from docs to code

`prothon execute` is an orchestrator that aligns source code to documentation in three phases:

1. **Plan** — reads all three docs plus generated reference skills, scans the codebase for gaps, and writes a `change_promise.toml` declaring every task with files, scope, dependencies, and context. You approve the plan before anything runs.
2. **Execute** — launches a fresh-context subagent per task. Each subagent implements, runs `poe check`, commits, and verifies its promise. Failed checks trigger up to 3 retries. Independent tasks can run in parallel.
3. **Verify** — launches a compliance-checker subagent for a full cross-reference of docs against code. The promise file is cleaned up only after everything passes.

Fresh-context subagents are the key design decision here — each task gets a clean context loaded with only the files and reference skills it needs, preventing context pollution between tasks.

---

## skills

Each command launches a dedicated Claude Code session with the corresponding skill. You make the decisions; the skill handles structure, research, and verification.

```
command              skill                 what it does
─────────────────────────────────────────────────────────────────────────────
prothon new          —                     scaffold a new project with full toolchain
prothon init         —                     adopt an existing project (docs + agent files only)
prothon spec         spec-writer           extract requirements through probing questions
prothon design       design-writer         research technologies, present trade-offs
prothon patterns     patterns-writer       define code patterns and testing conventions
prothon execute      execute               plan, delegate, and implement code from docs
prothon compliance   compliance-checker    verify code matches documentation
```

Three additional skills run automatically as quality gates — never invoked directly:

- **doc-harmonizer** — cross-references all doc levels after any doc is written, amends lower docs to resolve conflicts
- **tech-researcher** — generates reference skills for your chosen stack after DESIGN.md is written, using Context7 docs with web search fallback
- **promise system** — `prothon promise {plan,status,check,complete,cleanup}` tracks and verifies implementation tasks

## tooling

Generated projects ship with a full quality toolchain enforced on every commit (pre-commit hooks) and every push (CI). AI-generated code gets the same scrutiny as human code.

```
ruff           lint & format
ty             type checking
pytest         tests (+ hypothesis for property-based)
mutmut         mutation testing
bandit         security scanning
vulture        dead code detection
complexipy     complexity analysis
```

`poe check` runs everything locally. Pre-commit hooks ensure nothing bypasses them.

---

## why not just prompt better

The difference between prothon and "write a good system prompt" is structural enforcement:

- **Separation of concerns** — skills refuse to write content that belongs at a different level. The spec-writer won't discuss technology. The design-writer won't include code. This isn't a suggestion; the skills actively reject it.
- **Automated verification** — doc-harmonizer catches cross-level conflicts, compliance-checker catches code-vs-doc drift, promise checks catch implementation-vs-plan drift. Three independent verification loops, all automatic.
- **Fresh-context subagents** — each implementation task gets a clean context with only the files and skills it needs. No context pollution between tasks, no hallucinated state from earlier in a long conversation.
- **Durable authority** — `AGENTS.md` is checked into the repo and loaded by the AI on every interaction. Decisions survive across sessions, contributors, and tools. It's not in your chat history; it's in your repository.

## agent compatibility

`AGENTS.md` is the canonical instruction file, symlinked for automatic discovery:

```
AGENTS.md              ← canonical
CLAUDE.md  → AGENTS.md    Claude Code
GEMINI.md  → AGENTS.md    Gemini
AGENT.md   → AGENTS.md    other agents
```

Skills live in `.agents/skills/` with symlinks to `.claude/skills/` and `.opencode/skills/`.

## customizing the template

Template files live in `template/`. Jinja-templated files use `.jinja` extension. Generated projects include a `.copier-answers.yml` for update compatibility:

```bash
copier copy --trust --vcs-ref HEAD /path/to/prothon /tmp/test-project
```

## license

MIT
