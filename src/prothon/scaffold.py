"""Template rendering, copier answers, git init."""

from __future__ import annotations

import os
from pathlib import Path

from prothon.git import run_git


def get_template_dir() -> Path:
    """Return the path to the bundled template directory."""
    pkg_template = Path(__file__).resolve().parent / "template"
    if pkg_template.is_dir():
        return pkg_template
    # Development / mutmut: walk up to find template/ with copier.yml
    current = Path(__file__).resolve().parent
    while current != current.parent:
        candidate = current / "template"
        if candidate.is_dir() and (candidate / "copier.yml").exists():
            return candidate
        current = current.parent
    msg = "Cannot locate template directory"
    raise FileNotFoundError(msg)


def generate(dest: Path, data: dict | None = None) -> None:
    """Generate a project from the template using Copier.

    Args:
        dest: Destination directory for the generated project.
        data: Pre-filled answers dict. When provided, defaults=True
              is used to skip interactive prompts.
    """
    from copier import run_copy

    template = str(get_template_dir())
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
