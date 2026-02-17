# prothon

basecamp-research kmer-counting software assignment

## Documentation Hierarchy

This project uses a three-level documentation hierarchy. Documents are listed in order of authority — higher documents override lower ones when in conflict.

| Level | Document | Contains | Authority |
|-------|----------|----------|-----------|
| 1 | `docs/SPEC.md` | Requirements, constraints, scope | Highest |
| 2 | `docs/DESIGN.md` | Architecture, packages, interfaces | Medium |
| 3 | `docs/PATTERNS.md` | Code patterns, conventions, testing | Lowest |

**Rules:**
- SPEC.md must exist before DESIGN.md can be written
- DESIGN.md must exist before PATTERNS.md can be written
- When documents conflict, the higher-level document wins and lower documents must be amended

## Mandatory Development Workflow

All code changes — features, bug fixes, refactors — MUST follow this workflow:

### 1. Identify the Highest Affected Doc Level

- Does this change affect **requirements**? → Start at SPEC
- Does this change affect **architecture or packages**? → Start at DESIGN
- Does this change affect **code patterns**? → Start at PATTERNS
- Is this a **code-only change** with no doc impact? → Skip to step 5

### 2. Update Docs Top-Down

Starting from the highest affected level, tell the user to run the corresponding `prothon` CLI commands in order:

- SPEC-level change → `prothon spec`, then `prothon design`, then `prothon patterns`
- DESIGN-level change → `prothon design`, then `prothon patterns`
- PATTERNS-level change → `prothon patterns` only

Each command launches a separate Claude session. Do NOT invoke `/spec-writer`, `/design-writer`, or `/patterns-writer` directly — the user runs these via the CLI.

Doc harmonization and tech-researcher are handled automatically by the design-writer and patterns-writer skills as subagent quality gates. You do not need to trigger them manually.

### 5. Implement

Write the code changes.

### 6. Verify Compliance (Automatic)

**This is an always-on quality gate.** Before claiming any implementation work is complete, you MUST launch a **dedicated subagent** (using the Task tool) to verify code matches documentation. Do not perform this check inline — spawn a fresh subagent with the compliance-checker skill content so it gets a clean context focused solely on compliance verification. Report the subagent's findings to the user.

If the compliance check reports failures, fix the code or update docs and re-check.

For explicit full compliance scans, the user can run `uvx prothon compliance`.

## Skills Directory

Skills live in `.agents/skills/` as the canonical location. This directory is symlinked to both `.claude/skills/` and `.opencode/skills/` for automatic discovery by Claude Code and OpenCode respectively.

```
.agents/skills/           <- canonical location (edit here)
.claude/skills -> .agents/skills   <- symlink (auto-discovered by Claude Code)
.opencode/skills -> .agents/skills <- symlink (auto-discovered by OpenCode)
```

When creating new skills, always place them in `.agents/skills/<skill-name>/SKILL.md`. The symlinks ensure both tools discover them automatically.

## Conventions

- **Package manager:** uv
- **Task runner:** poe (poethepoet)
- **Linting:** ruff (linting + formatting)
- **Type checking:** ty
- **Testing:** pytest + hypothesis
- **Security:** bandit
- **Dead code:** vulture
- **Complexity:** complexipy
- **Pre-commit:** hooks enforce all checks on every commit

Run `poe check` before committing to verify all quality checks pass.
