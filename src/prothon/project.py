"""Project root detection and shared project context."""

from __future__ import annotations

from pathlib import Path

from prothon.exceptions import ProjectNotFoundError


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from start directory to find a prothon project root.

    Looks for ``docs/SPEC.md`` in the start directory and each
    ancestor. Returns the first directory containing the marker file.

    Args:
        start: Directory to begin searching from. Defaults to the
            current working directory.

    Returns:
        Path to the project root.

    Raises:
        ProjectNotFoundError: If the filesystem root is reached without
            finding a project marker.
    """
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / "docs" / "SPEC.md").is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise ProjectNotFoundError(
        "no prothon project found (no docs/SPEC.md in parent directories)"
    )
