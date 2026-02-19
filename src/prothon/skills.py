"""Skill discovery and symlink management."""

from __future__ import annotations

import shutil
from pathlib import Path


def bundled_skills_dir() -> Path:
    """Return the path to the bundled skills directory."""
    return Path(__file__).parent / "skills"


def sync_skills(target: Path | None = None) -> None:
    """Symlink bundled skills into the target directory so the assistant discovers them.

    Args:
        target: Directory to symlink skills into. Defaults to
            ``~/.claude/skills/`` for Claude Code discovery.
    """
    if target is None:
        target = Path.home() / ".claude" / "skills"

    bundled = bundled_skills_dir()
    if not bundled.is_dir():
        return

    target.mkdir(parents=True, exist_ok=True)

    for skill_dir in bundled.iterdir():
        if not skill_dir.is_dir():
            continue
        dest = target / skill_dir.name
        if dest.is_symlink():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        dest.symlink_to(skill_dir.resolve())
