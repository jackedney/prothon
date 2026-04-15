<div align="center">

<img src="https://raw.githubusercontent.com/jackedney/prothon/master/docs/logo.svg" alt="PROTHON" width="480"/>

**docs-first project generator for AI-assisted Python development**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/installer-uv-blueviolet.svg)](https://docs.astral.sh/uv/)

</div>

&nbsp;

AI alignment isn't about better prompts — it's about giving AI a **durable source of truth** and a **verification loop** that catches when code drifts from intent.

```text
    SPEC.md  ──→  DESIGN.md  ──→  PATTERNS.md  ──→  code
  requirements    architecture     conventions      implementation
   (highest)                                         (verified)
```

---

### install

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv tool install "git+https://github.com/jackedney/prothon"
```

### quickstart

**new project**

```bash
prothon new my-project && cd my-project && uv sync
prothon spec       # define requirements   → SPEC.md
prothon design     # choose architecture   → DESIGN.md
prothon patterns   # set conventions       → PATTERNS.md
prothon execute    # implement code from docs
```

**existing project**

```bash
cd your-existing-repo
prothon init       # overlay docs-first workflow (creates docs/, AGENTS.md, symlinks)
prothon spec && prothon design && prothon patterns && prothon execute
```

Each command launches an AI assistant session with a dedicated skill. The skill asks you questions, researches options, and writes the doc. You make the decisions. Works with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (default) and [opencode](https://opencode.ai).

---

## 01 — hierarchical documentation

Three documents with strict authority. Higher overrides lower. Each has a dedicated conversational skill that presents one decision at a time and **hard-rejects** content belonging at a different level.

```text
docs/
├── SPEC.md        # requirements & constraints        (highest authority)
├── DESIGN.md      # architecture & technology choices
└── PATTERNS.md    # code conventions & testing         (lowest authority)
```

→ Skills **hard-reject** content from other levels — the spec-writer won't discuss technology, the design-writer won't include code snippets
→ SPEC change triggers DESIGN review, then PATTERNS review
→ Conflicts resolve at doc level **before** code is written
→ After `design` or `patterns`, the **harmonizer** cross-references all three levels automatically

### changes cascade top-down

```text
requirement changes  →  prothon spec  →  prothon design  →  prothon patterns  →  implement
design changes       →                   prothon design  →  prothon patterns  →  implement
convention changes   →                                      prothon patterns  →  implement
```

---

## 02 — drift detection & reconciliation

Three independent verification loops, all automatic.

→ **doc-harmonizer** — fires after `design` or `patterns` to catch contradictions, scope creep, unchosen tech between doc levels. Amends lower docs. SPEC is never touched.
→ **compliance-checker** — reads every checkable statement from docs and verifies code implements it. Produces PASS/FAIL/PARTIAL tables with `file:line` evidence. Always-on quality gate.
→ **change promises** — `change_promise.toml` declares exactly what files each task will create, modify, or remove with expected line counts. `prothon promise check` diffs against the base commit to verify what actually happened.

Documentation files are protected by **edit guards** — only the designated skill (spec-writer, design-writer, patterns-writer, refactor, doc-harmonizer) may modify each doc. Each write is committed immediately to prevent overwrites.

---

## 03 — the AI learns your stack

When you change the Technology Choices or Key Decisions tables in DESIGN.md, the **tech-researcher** fires automatically — queries Context7 live docs, falls back to web search, then training knowledge. Generates reference skills for your exact stack:

```text
.agents/skills/
├── tech-*.md      # library usage, idioms, gotchas, version-specific APIs
├── style-*.md     # naming conventions, import organization, type annotations
├── optim-*.md     # performance patterns, GPU batching, subprocess management
└── domain-*.md    # field-specific concepts: geospatial, ML, finance, etc.
```

Auto-loaded during execution — no manual context switching.

---

## 04 — wave-based execution

Before execution starts, the planner writes `change_promise.toml` — a contract that turns open-ended code generation into a bounded, verifiable process.

→ Files to create, modify, remove — declared upfront
→ Line predictions force **thinking through scope**
→ Checked against git with ±30% or ±30 lines tolerance
→ 3 attempts per task, **fresh context** each

Execution runs in **phase-based waves**. The executor inspects current code vs docs, determines the next phase, spawns fresh subagents for a batch of independent tasks, runs a compliance check, then loops. Independent tasks within a wave run in parallel with file-locking safety (`fcntl.flock` / `msvcrt.locking`) and atomic writes to prevent partial reads.

Fresh-context subagents are the key design decision — each task gets a clean context loaded with only the files and skills it needs, preventing context pollution between tasks.

---

## 05 — skills

Each command launches a dedicated session. You make the decisions; the skill handles structure, research, and verification.

```text
command              skill                 what it does
─────────────────────────────────────────────────────────────────────────────
prothon new          —                     scaffold a new project with full toolchain
prothon init         —                     overlay docs-first workflow on existing project
prothon spec         spec-writer           extract requirements through probing questions
prothon design       design-writer         research technologies, present trade-offs
prothon patterns     patterns-writer       define code patterns and testing conventions
prothon execute      execute               plan, delegate, and implement code from docs
prothon refactor     refactor              doc-driven refactoring of code and documentation
prothon compliance   compliance-checker    verify code matches documentation
```

Three additional skills run automatically as quality gates — never invoked directly:

→ **doc-harmonizer** — cross-references all doc levels after `design` or `patterns`, amends lower docs to resolve conflicts
→ **tech-researcher** — generates reference skills from Context7 docs with web search fallback when Technology Choices or Key Decisions tables change
→ **promise system** — `prothon promise {plan,status,check,complete,record-attempt,cleanup}` tracks and verifies tasks

---

## 06 — semantic versioning

Version bumps are automatic based on which documentation level changed:

```text
SPEC.md change       →  major bump  (breaking requirements)
DESIGN.md change     →  minor bump  (architecture change)
PATTERNS.md / code   →  patch bump  (conventions or implementation)
```

A CI workflow generates version bumps on pull requests to master. Skills use canonical subagent type names (`general-purpose`, `explore`, `plan`) that each backend translates to its own naming scheme, keeping skills portable across assistants.

---

## 07 — tooling

Full quality toolchain enforced on every commit and every push. AI-generated code gets the same scrutiny as human code.

```text
ruff           lint & format
ty             type checking
pytest         tests (+ hypothesis for property-based)
mutmut         mutation testing
bandit         security scanning
vulture        dead code detection
complexipy     complexity analysis
```

`uv run poe check` runs everything. Pre-commit hooks ensure nothing bypasses them.

---

## why not just prompt better

→ **Separation of concerns** — skills refuse to write content that belongs at a different level. This isn't a suggestion; the skills actively reject it.
→ **Automated verification** — three independent verification loops catch cross-level conflicts, code-vs-doc drift, and implementation-vs-plan drift. All automatic.
→ **Fresh-context subagents** — each task gets a clean context with only the files and skills it needs. No context pollution, no hallucinated state.
→ **Durable authority** — `AGENTS.md` is checked into the repo and loaded on every interaction. Decisions survive across sessions, contributors, and tools. It's not in your chat history; it's in your repository.

### agent compatibility

`AGENTS.md` is the canonical instruction file, symlinked for automatic discovery:

```text
AGENTS.md              ← canonical
CLAUDE.md  → AGENTS.md    Claude Code
GEMINI.md  → AGENTS.md    Gemini
AGENT.md   → AGENTS.md    other agents
```

Built-in Prothon skills (`prothon-*`) live in `src/prothon/skills/` and are symlinked into each assistant's discovery directory on every CLI invocation. Project-specific reference skills (generated by `prothon design`) are stored in `.agents/skills/`.

### assistant selection

```bash
prothon --assistant opencode spec    # CLI flag (highest priority)
PROTHON_ASSISTANT=opencode prothon spec   # env var
```

Or set it permanently in `pyproject.toml`:

```toml
[tool.prothon]
assistant = "opencode"
```

Or globally in `$XDG_CONFIG_HOME/prothon/config.toml` (defaults to `~/.config/prothon/config.toml`):

```toml
assistant = "opencode"
```

Priority: CLI flag > env var > pyproject.toml > global config > default (`claude-code`).

### customizing the template

Template files live in `template/`. Jinja-templated files use `.jinja` extension. Generated projects include a `.copier-answers.yml` for update compatibility:

```bash
copier copy --trust --vcs-ref HEAD /path/to/prothon /tmp/test-project
```

---

## future

→ **additional coding agents** — currently supports [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [opencode](https://opencode.ai). Planned support for other agent backends.
→ **code review integration** — integrate with [CodeRabbit](https://coderabbit.ai) and [Greptile](https://greptile.com) to bring automated, doc-aware code review into the workflow.
→ **continuous agentic development** — autonomous development cycles — agents read docs, plan, implement, verify, and loop until the task is complete, with minimal human intervention.

---

MIT
