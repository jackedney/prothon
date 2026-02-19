"""Project root detection and shared project context."""

from __future__ import annotations

from pathlib import Path

from prothon.exceptions import ProjectNotFoundError  # noqa: F401


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find a prothon project root.

    Looks for `.copier-answers.yml` in the start directory and each
    ancestor. Returns the first directory containing the marker file,
    or ``None`` if the filesystem root is reached without finding one.

    Args:
        start: Directory to begin searching from. Defaults to the
            current working directory.

    Returns:
        Path to the project root, or None if not found.
    """
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".copier-answers.yml").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
