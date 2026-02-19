"""Abstract assistant interface, backend registry, and launch lifecycle."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from prothon.exceptions import AssistantNotFoundError, UnknownBackendError


class AssistantBackend(Protocol):
    """Contract that every assistant backend must satisfy structurally."""

    @property
    def name(self) -> str: ...

    @property
    def cli_command(self) -> str: ...

    def build_command(self, skill_name: str) -> list[str]: ...

    def sync_skills(self) -> None: ...


class ClaudeCodeBackend:
    """Claude Code assistant backend — invokes the ``claude`` CLI."""

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def cli_command(self) -> str:
        return "claude"

    def build_command(self, skill_name: str) -> list[str]:
        """Build the subprocess argv for launching a Claude Code session.

        Args:
            skill_name: The skill to invoke (e.g. ``"prothon-spec-writer"``).

        Returns:
            Command list suitable for ``subprocess.run()``.
        """
        return [self.cli_command, "--dangerously-skip-permissions", f"/{skill_name}"]

    def sync_skills(self) -> None:
        """Symlink bundled skills into Claude Code's discovery directory."""
        from prothon.skills import sync_skills

        sync_skills()


_BACKENDS: dict[str, type] = {
    "claude-code": ClaudeCodeBackend,
}


def get_backend(name: str = "claude-code") -> AssistantBackend:
    """Look up a backend by registry key and return an instance.

    Args:
        name: Registry key (default ``"claude-code"``).

    Returns:
        A fresh backend instance satisfying ``AssistantBackend``.

    Raises:
        UnknownBackendError: If *name* is not in the registry.
    """
    cls = _BACKENDS.get(name)
    if cls is None:
        raise UnknownBackendError(f"no backend registered for '{name}'")
    return cls()


def launch(backend: AssistantBackend, skill_name: str, cwd: Path) -> int:
    """Check the binary, sync skills, and run the assistant subprocess.

    Args:
        backend: The assistant backend to use.
        skill_name: Skill to invoke inside the session.
        cwd: Working directory for the subprocess.

    Returns:
        The subprocess exit code.

    Raises:
        AssistantNotFoundError: If the backend binary is not on PATH.
    """
    if not shutil.which(backend.cli_command):
        raise AssistantNotFoundError(f"{backend.cli_command} not found on PATH")
    backend.sync_skills()
    return subprocess.run(backend.build_command(skill_name), cwd=cwd).returncode
