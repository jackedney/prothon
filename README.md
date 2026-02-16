<div align="center">

```
 █▀▀▄ █▀▀▄ ▄▀▀▄ ▀█▀ █  █ ▄▀▀▄ █▄  █
 █▄▄█ █▄▄▀ █  █  █  █▄▄█ █  █ █ █ █
 █    █  █ ▀▄▄▀  █  █  █ ▀▄▄▀ █  ▀█ ●
```

**docs-first project generator for AI-assisted Python development**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/installer-uv-blueviolet.svg)](https://docs.astral.sh/uv/)

</div>

&nbsp;

Most AI-generated projects start with no structure. The AI writes code with no shared understanding of requirements, architecture, or conventions. As features are added and requirements change, there's no source of truth. Every prompt becomes a fresh negotiation and the AI drifts further from your intent.

prothon generates projects with a documentation hierarchy that the AI treats as its instructions, and a toolchain that enforces they stay in sync with the code.

```
            ┌──────────────────────────────────────────┐
            │                                          │
            │  SPEC  ->  DESIGN  ->  PATTERNS  ->  code│
            │   ▲          ▲           ▲               │
            │   skills guide each phase                │
            │                                          │
            └──────────────────────────────────────────┘
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

```bash
cd my-project
uv sync
prothon spec       # define requirements   (writes SPEC.md)
prothon design     # choose architecture   (writes DESIGN.md)
prothon patterns   # set conventions       (writes PATTERNS.md)
```

Each command launches a Claude Code session with the corresponding skill. The skill asks you questions, researches options, and writes the doc. You make the decisions.

Once your docs are in place, Claude Code has full context via `CLAUDE.md` and follows the documented hierarchy for all future work.

---

## how it works

AI coding assistants lose alignment over time. Early on the AI knows what you want, but as requirements change and features pile up, it starts making assumptions. It picks the wrong patterns, contradicts earlier decisions, or ignores constraints you set weeks ago. Without a shared source of truth, every prompt is a fresh negotiation.

prothon solves this with a documentation hierarchy that the AI treats as its instructions:

```
docs/
├── SPEC.md        # requirements & constraints        (highest authority)
├── DESIGN.md      # architecture & technology choices
└── PATTERNS.md    # code conventions & testing         (lowest authority)
```

Higher levels override lower ones. This matters when things change, and they always do.

### changes cascade top-down

When a requirement changes, you update SPEC.md. That may invalidate a design decision in DESIGN.md, which may invalidate a convention in PATTERNS.md. The hierarchy enforces that you resolve these cascades before writing code, so the AI never implements against stale decisions.

```
requirement changes -> update SPEC -> review DESIGN -> review PATTERNS -> implement
design changes      ->               update DESIGN -> review PATTERNS -> implement
convention changes  ->                               update PATTERNS -> implement
```

### docs stay in sync with code

Two automated checks close the loop:

- **doc-harmonizer** runs after any doc change and detects conflicts between levels. If DESIGN.md contradicts SPEC.md, you find out before a line of code is written.
- **compliance-checker** runs before work is declared complete and verifies the code actually implements what the docs describe, catching drift before it compounds.

### the AI learns your stack

When you choose technologies in DESIGN.md, **tech-researcher** generates reference skills: up-to-date documentation, idioms, and best practices for the specific libraries in your project. The AI doesn't just know your requirements. It has current reference material for the tools you chose to implement them with.

The result: the AI reads your docs on every interaction, follows the hierarchy, and gets checked against it. Requirements, architecture, conventions, and code stay aligned as the project evolves, not just at the start but through every change.

---

## skills

```
prothon spec         spec-writer          extract requirements through probing questions
prothon design       design-writer        research technologies, present trade-offs
prothon patterns     patterns-writer      define code patterns and testing conventions
prothon compliance   compliance-checker   verify code matches documentation
```

Two additional skills run automatically: **doc-harmonizer** (detects conflicts between doc levels) and **tech-researcher** (generates reference material for your chosen stack).

## tooling

AI-generated code needs stronger guardrails, not weaker ones. Generated projects ship with a full quality toolchain that runs on every commit via pre-commit hooks and on every push via CI. Bad code from any source, human or AI, gets caught before it lands.

```
ruff           lint & format
ty             type checking
pytest         tests (+ hypothesis for property-based)
mutmut         mutation testing
bandit         security scanning
vulture        dead code detection
complexipy     complexity analysis
```

Run `poe check` to execute all checks locally. Pre-commit hooks ensure nothing bypasses them.

---

## customizing the template

Template files live in `template/`. Jinja-templated files use `.jinja` extension.

```bash
copier copy --trust --vcs-ref HEAD /path/to/prothon /tmp/test-project
```

## license

MIT
