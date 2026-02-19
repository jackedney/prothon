"""Orchestrator: task planning, subagent dispatch."""

from __future__ import annotations

from pathlib import Path


def run(project_root: Path) -> None:
    """Plan tasks and dispatch subagents for execution.

    Args:
        project_root: Root directory of the prothon project.

    Raises:
        NotImplementedError: Always — execution is handled by a skill.
    """
    _ = project_root  # interface stub; parameter used once implemented
    msg = "Execution is handled by the prothon-execute skill. Run: uvx prothon execute"
    raise NotImplementedError(msg)
