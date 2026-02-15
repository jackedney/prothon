# uvx CLI Tool Design

**Goal:** Make `uvx perfect-python my-project` work as a standalone project generator — no copier runtime dependency, interactive prompts, Jinja2 templating directly.

## CLI Interface

```bash
uvx perfect-python my-project
# Prompts: module_name, description, author_name, author_email, python_version, license
```

## Structure Changes

```
perfect-python/
├── pyproject.toml              # NEW: CLI package config
├── src/
│   └── perfect_python/
│       ├── __init__.py
│       └── cli.py              # CLI: prompts + generation logic
├── template/                   # Unchanged (still works with copier too)
├── copier.yml                  # Unchanged (for copier update)
└── README.md
```

## How It Works

1. `typer.prompt()` collects variables (project_name from CLI arg, rest interactive with defaults/choices)
2. Walk `template/` — render `.jinja` files with Jinja2, copy others as-is
3. Create symlinks (CLAUDE.md, GEMINI.md, AGENT.md → AGENTS.md)
4. Write `.copier-answers.yml` so `copier update` works later
5. `git init && git add . && git commit`

## Dependencies

- `typer` (CLI + prompts)
- `jinja2` (templating)

## Packaging

- Build backend: hatchling
- Entry point: `perfect-python = "perfect_python.cli:app"`
- Template files bundled via hatchling `force-include`
- `copier.yml` stays at repo root for copier users
