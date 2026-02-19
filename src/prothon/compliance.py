"""Doc-vs-code verification and reporting."""

from __future__ import annotations

from pathlib import Path


def check(project_root: Path) -> None:
    """Run compliance verification against project documentation.

    Args:
        project_root: Root directory of the prothon project.

    Raises:
        NotImplementedError: Always — compliance is handled by a skill.
    """
    _ = project_root  # interface stub; parameter used once implemented
    msg = (
        "Compliance checking is handled by the prothon-compliance-checker skill."
        " Run: uvx prothon compliance"
    )
    raise NotImplementedError(msg)
