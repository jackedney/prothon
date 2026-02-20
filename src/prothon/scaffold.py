"""Template rendering, copier answers, git init, project adoption."""

from __future__ import annotations

import os
from pathlib import Path

from prothon.exceptions import GitError, ProjectAlreadyInitError
from prothon.git import run_git

_SPEC_SCAFFOLD = """\
# Project Specification

## Purpose

## Requirements

## Constraints

## Out of Scope
"""

_DESIGN_SCAFFOLD = """\
# Design Document

## Architecture

## Technology Choices

## Interfaces

## Key Decisions
"""

_PATTERNS_SCAFFOLD = """\
# Implementation Patterns

## Code Organization

## Design Patterns

## Error Handling

## Testing Patterns
"""

_AGENTS_CONTENT = """\
# Project

## Documentation Hierarchy

This project uses a three-level documentation hierarchy. Documents are listed \
in order of authority — higher documents override lower ones when in conflict.

| Level | Document | Contains | Authority |
|-------|----------|----------|-----------|
| 1 | `docs/SPEC.md` | Requirements, constraints, scope | Highest |
| 2 | `docs/DESIGN.md` | Architecture, packages, interfaces | Medium |
| 3 | `docs/PATTERNS.md` | Code patterns, conventions, testing | Lowest |

**Rules:**
- SPEC.md must exist before DESIGN.md can be written
- DESIGN.md must exist before PATTERNS.md can be written
- When documents conflict, the higher-level document wins and lower documents \
must be amended

## Mandatory Development Workflow

All code changes — features, bug fixes, refactors — MUST follow this workflow:

### 1. Identify the Highest Affected Doc Level

- Does this change affect **requirements**? → Start at SPEC
- Does this change affect **architecture or packages**? → Start at DESIGN
- Does this change affect **code patterns**? → Start at PATTERNS
- Is this a **code-only change** with no doc impact? → Skip to step 5

### 2. Update Docs Top-Down

Starting from the highest affected level, tell the user to run the \
corresponding `prothon` CLI commands in order:

- SPEC-level change → `prothon spec`, then `prothon design`, then \
`prothon patterns`
- DESIGN-level change → `prothon design`, then `prothon patterns`
- PATTERNS-level change → `prothon patterns` only

Each command launches a separate Claude session. Do NOT invoke \
`/spec-writer`, `/design-writer`, or `/patterns-writer` directly — the user \
runs these via the CLI.

Doc harmonization and tech-researcher are handled automatically by the \
design-writer and patterns-writer skills as subagent quality gates. You do \
not need to trigger them manually.

### 5. Implement

Write the code changes.

### 6. Verify Compliance (Automatic)

**This is an always-on quality gate.** Before claiming any implementation \
work is complete, you MUST launch a **dedicated subagent** (using the Task \
tool) to verify code matches documentation. Do not perform this check \
inline — spawn a fresh subagent with the compliance-checker skill content so \
it gets a clean context focused solely on compliance verification. Report the \
subagent's findings to the user.

If the compliance check reports failures, fix the code or update docs and \
re-check.

For explicit full compliance scans, the user can run `uvx prothon compliance`.

## Skills Directory

Skills live in `.agents/skills/` as the canonical location. This directory \
is symlinked to both `.claude/skills/` and `.opencode/skills/` for automatic \
discovery by Claude Code and OpenCode respectively.

```
.agents/skills/           <- canonical location (edit here)
.claude/skills -> .agents/skills   <- symlink (auto-discovered by Claude Code)
.opencode/skills -> .agents/skills <- symlink (auto-discovered by OpenCode)
```

When creating new skills, always place them in \
`.agents/skills/<skill-name>/SKILL.md`. The symlinks ensure both tools \
discover them automatically.

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
"""


def _template_dir() -> Path:
    """Return the path to the bundled template directory."""
    pkg_template = Path(__file__).parent / "template"
    if pkg_template.is_dir():
        return pkg_template
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "template"


def generate(dest: Path, data: dict | None = None) -> None:
    """Generate a project from the template using Copier.

    Args:
        dest: Destination directory for the generated project.
        data: Pre-filled answers dict. When provided, defaults=True
              is used to skip interactive prompts.
    """
    from copier import run_copy

    template = str(_template_dir())
    run_copy(
        template,
        str(dest),
        data=data,
        defaults=bool(data),
        unsafe=True,
        vcs_ref="HEAD",
    )
    _post_generate(dest)


def _post_generate(dest: Path) -> None:
    """Post-generation steps: symlinks, agent dirs, git init.

    Args:
        dest: The generated project root directory.
    """
    # Create symlinks for agent instruction files
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = dest / name
        if not link.exists():
            os.symlink("AGENTS.md", link)

    # Create .agents/skills for project-specific reference skills
    (dest / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

    # Initialize git
    run_git("init", cwd=dest)
    run_git("add", ".", cwd=dest)
    run_git("commit", "-m", "Initial commit from prothon template", cwd=dest)


def init_existing(cwd: Path | None = None) -> list[Path]:
    """Overlay the docs-first workflow onto an existing project.

    Args:
        cwd: Directory to adopt. Defaults to the current working directory.

    Returns:
        List of created file paths.

    Raises:
        GitError: If the directory is not a git repository.
        ProjectAlreadyInitError: If docs/SPEC.md already exists.
    """
    root = Path(cwd) if cwd else Path.cwd()

    # Guard: must be a git repository
    try:
        run_git("rev-parse", "--git-dir", cwd=root)
    except GitError:
        raise GitError(f"not a git repository: {root}") from None

    # Guard: must not already be initialized
    spec_path = root / "docs" / "SPEC.md"
    if spec_path.exists():
        raise ProjectAlreadyInitError(f"docs/SPEC.md already exists in {root}")

    created: list[Path] = []

    # Create docs/ directory and write scaffolds
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    scaffolds = {
        "SPEC.md": _SPEC_SCAFFOLD,
        "DESIGN.md": _DESIGN_SCAFFOLD,
        "PATTERNS.md": _PATTERNS_SCAFFOLD,
    }
    for filename, content in scaffolds.items():
        path = docs_dir / filename
        path.write_text(content)
        created.append(path)

    # Create AGENTS.md at project root
    agents_path = root / "AGENTS.md"
    agents_path.write_text(_AGENTS_CONTENT)
    created.append(agents_path)

    # Create symlinks: CLAUDE.md, GEMINI.md, AGENT.md -> AGENTS.md
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = root / name
        if link.is_symlink():
            link.unlink()
        os.symlink("AGENTS.md", link)
        created.append(link)

    # Create .agents/skills/ directory
    skills_dir = root / ".agents" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    created.append(skills_dir)

    return created
