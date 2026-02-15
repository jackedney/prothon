# prothon

Copier template for Python projects with docs-first AI workflow. Generated projects ship with a documentation hierarchy, agent skills, and quality tooling — ready for Claude Code from the first commit.

## Quick Start

Requires [uv](https://docs.astral.sh/uv/).

```bash
uvx --from git+https://github.com/jackedney/prothon prothon my-project
cd my-project
uv sync
poe check
```

Or with [Copier](https://copier.readthedocs.io/) directly:

```bash
copier copy --trust gh:jackedney/prothon my-project
```

## What You Get

```
my-project/
├── AGENTS.md                      # AI agent instructions
├── CLAUDE.md -> AGENTS.md         # Symlinks for AI agents
├── GEMINI.md -> AGENTS.md
├── AGENT.md -> AGENTS.md
├── docs/
│   ├── SPEC.md                    # Requirements (highest authority)
│   ├── DESIGN.md                  # Architecture & tech choices
│   ├── PATTERNS.md                # Code conventions (lowest authority)
│   └── skills/                    # Agent skill definitions
│       ├── spec-writer.md
│       ├── design-writer.md
│       ├── tech-researcher.md
│       ├── patterns-writer.md
│       ├── doc-harmonizer.md
│       └── compliance-checker.md
├── src/<module>/
├── tests/
├── pyproject.toml
├── .pre-commit-config.yaml
└── .github/workflows/ci.yml
```

**Tooling:** ruff (lint/format), ty (types), pytest + hypothesis (tests), mutmut (mutation testing), bandit (security), vulture (dead code), complexipy (complexity). All enforced via pre-commit hooks and CI.

## Using with Claude Code

`CLAUDE.md` symlinks to `AGENTS.md`, giving Claude full context automatically. The workflow is **document before you code** — three doc levels form a hierarchy where higher levels override lower ones.

### Initial Setup

Tell Claude to read each skill file and follow its instructions:

```
1. Read docs/skills/spec-writer.md — populate SPEC.md (requirements)
2. Read docs/skills/design-writer.md — populate DESIGN.md (architecture)
3. Read docs/skills/tech-researcher.md — generate reference skills for chosen packages
4. Read docs/skills/patterns-writer.md — populate PATTERNS.md (conventions)
```

### Ongoing Changes

1. Update docs top-down from the highest affected level
2. Generate tech skills if design changed
3. Harmonize (`docs/skills/doc-harmonizer.md`)
4. Implement
5. Verify compliance (`docs/skills/compliance-checker.md`)

## Customizing the Template

Template files live in `template/`. Jinja-templated files use `.jinja` extension. Test changes locally:

```bash
copier copy --trust --vcs-ref HEAD /path/to/prothon /tmp/test-project
```

## License

MIT
