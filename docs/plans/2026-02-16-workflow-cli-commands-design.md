# Workflow CLI Commands Design

## Summary

Add 4 subcommands to the `prothon` CLI that launch interactive Claude Code sessions for each development workflow stage. Also update the writer skills to handle existing docs and make the harmonizer an always-on quality gate in AGENTS.md.

## Commands

| Command | Skill | Purpose |
|---------|-------|---------|
| `uvx prothon new <dest>` | — | Generate a new project (existing behavior, renamed from default) |
| `uvx prothon spec` | spec-writer | Write or revise SPEC.md |
| `uvx prothon design` | design-writer → tech-researcher | Write or revise DESIGN.md, then auto-chain tech-researcher |
| `uvx prothon patterns` | patterns-writer | Write or revise PATTERNS.md |
| `uvx prothon compliance` | compliance-checker | Verify code matches docs |

Default command (no subcommand, positional arg) still generates a project.

## How Commands Work

Each workflow command:

1. Validates it's inside a prothon-generated project (checks for `.copier-answers.yml` in current or parent directories)
2. Validates `claude` CLI is on PATH
3. Reads `.agents/skills/<skill-name>/SKILL.md` from the project
4. Runs `claude --prompt "<skill content>"` as a subprocess, inheriting stdio for full interactivity

### Design Command Chaining

The `design` command chains two Claude sessions:
1. First session: design-writer skill (interactive, user writes DESIGN.md)
2. After first session exits: automatically launches tech-researcher skill (generates reference docs for chosen technologies)

The chaining happens in the CLI — the skill files themselves stay clean.

## Skill File Updates

### Existing Doc Handling

All three writer skills (spec-writer, design-writer, patterns-writer) need an "Existing Doc" section added to their process:

- If the target doc exists and is populated → read it first, present current content, ask what the user wants to change, work through revisions section by section
- If the target doc is empty/scaffold only → treat as creation (current behavior)

This ensures `uvx prothon spec` works correctly whether the user is creating SPEC.md for the first time or revising it later.

### Prerequisite Guards

The skills already have prerequisite checks (design requires SPEC.md, patterns requires both). No CLI-side pre-validation needed — the skill handles it inside the Claude session.

## AGENTS.md Update

### Harmonizer as Always-On Gate

Instead of a standalone command, the doc-harmonizer becomes an always-on quality gate baked into AGENTS.md. After any documentation modification, Claude/OpenCode should automatically check for consistency between doc levels without requiring manual `/doc-harmonizer` invocation.

### Compliance as Both

Compliance-checker remains both:
- An always-on gate in AGENTS.md (Claude checks compliance before claiming work is done)
- A standalone `uvx prothon compliance` command for explicit full scans

## Project Detection

Commands look for `.copier-answers.yml` starting from the current directory and walking up parent directories. If not found, exit with:

```
Error: Not inside a prothon-generated project.
Generate one with: uvx prothon my-project
```

## Claude CLI Dependency

If `claude` is not found on PATH, exit with:

```
Error: Claude Code CLI not found.
Install: https://docs.anthropic.com/en/docs/claude-code
```

## CLI Structure Change

Current structure:
```python
app = typer.Typer()

@app.command()
def main(destination): ...  # single default command
```

New structure:
```python
app = typer.Typer()

@app.command()
def new(destination): ...   # renamed from main

@app.command()
def spec(): ...
@app.command()
def design(): ...
@app.command()
def patterns(): ...
@app.command()
def compliance(): ...
```

The `new` command contains the existing generation logic. A default callback or typer configuration preserves `uvx prothon my-project` working without the `new` subcommand.

## Files Changed

1. `src/prothon/cli.py` — add subcommands, project detection, claude launching
2. `template/.agents/skills/spec-writer/SKILL.md` — add existing doc handling
3. `template/.agents/skills/design-writer/SKILL.md` — add existing doc handling
4. `template/.agents/skills/patterns-writer/SKILL.md` — add existing doc handling
5. `template/AGENTS.md.jinja` — add harmonizer as always-on gate, strengthen compliance gate
6. `tests/test_generate.py` — add tests for new CLI commands
