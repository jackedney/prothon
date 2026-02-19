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
        """Return subprocess argv for a Claude Code session with *skill_name*."""
        return [self.cli_command, "--dangerously-skip-permissions", f"/{skill_name}"]

    def sync_skills(self) -> None:
        """Symlink bundled skills into Claude Code's discovery directory."""
        from prothon.skills import sync_skills

        sync_skills()


_BACKENDS: dict[str, type] = {
    "claude-code": ClaudeCodeBackend,
}


def get_backend(name: str = "claude-code") -> AssistantBackend:
    """Return a backend instance for *name*, or raise UnknownBackendError."""
    cls = _BACKENDS.get(name)
    if cls is None:
        raise UnknownBackendError(f"no backend registered for '{name}'")
    return cls()


def launch(backend: AssistantBackend, skill_name: str, cwd: Path) -> int:
    """Check binary, sync skills, run the assistant, and return exit code."""
    if not shutil.which(backend.cli_command):
        raise AssistantNotFoundError(f"{backend.cli_command} not found on PATH")
    backend.sync_skills()
    return subprocess.run(backend.build_command(skill_name), cwd=cwd).returncode
