"""Abstract assistant interface, backend registry, and launch lifecycle."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from prothon.exceptions import AssistantNotFoundError, ProthonError, UnknownBackendError


class AssistantBackend(Protocol):
    """Contract that every assistant backend must satisfy structurally."""

    @property
    def name(self) -> str: ...

    @property
    def cli_command(self) -> str: ...

    @property
    def install_hint(self) -> str: ...

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]: ...

    def sync_skills(self) -> None: ...

    def env_overrides(self) -> dict[str, str]: ...

    def subagent_type_map(self) -> dict[str, str]: ...


class ClaudeCodeBackend:
    """Claude Code assistant backend — invokes the ``claude`` CLI."""

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def cli_command(self) -> str:
        return "claude"

    @property
    def install_hint(self) -> str:
        return "https://docs.anthropic.com/en/docs/claude-code"

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]:
        """Return subprocess argv for a Claude Code session with *skill_name*."""
        return [self.cli_command, "--dangerously-skip-permissions", f"/{skill_name}"]

    def sync_skills(self) -> None:
        """Symlink bundled skills into Claude Code's discovery directory."""
        from prothon.skills import sync_skills

        sync_skills(target=Path.home() / ".claude" / "skills")

    def env_overrides(self) -> dict[str, str]:
        """Return extra environment variables for Claude Code sessions."""
        return {}

    def subagent_type_map(self) -> dict[str, str]:
        """Return mapping from canonical subagent types to Claude Code names."""
        return {
            "general-purpose": "general-purpose",
            "explore": "Explore",
            "plan": "Plan",
        }


class OpenCodeBackend:
    """opencode assistant backend — invokes the ``opencode`` CLI."""

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def cli_command(self) -> str:
        return "opencode"

    @property
    def install_hint(self) -> str:
        return "https://opencode.ai"

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]:
        """Return subprocess argv for an opencode session with *skill_name*."""
        cmd = [self.cli_command, "--prompt", f"/{skill_name}"]
        if model is not None:
            cmd.extend(["--model", model])
        return cmd

    def sync_skills(self) -> None:
        """Symlink bundled skills into opencode's discovery directory."""
        from prothon.skills import sync_skills

        raw_xdg = os.environ.get("XDG_CONFIG_HOME")
        xdg = (
            Path(raw_xdg)
            if raw_xdg and Path(raw_xdg).is_absolute()
            else Path.home() / ".config"
        )
        sync_skills(target=xdg / "opencode" / "skills")

    def env_overrides(self) -> dict[str, str]:
        """Return extra environment variables for opencode sessions."""
        return {}

    def subagent_type_map(self) -> dict[str, str]:
        """Return mapping from canonical subagent types to opencode names."""
        return {"general-purpose": "general", "explore": "explore", "plan": "plan"}


class GeminiCLIBackend:
    """Gemini CLI assistant backend — invokes the ``gemini`` CLI."""

    @property
    def name(self) -> str:
        return "Gemini CLI"

    @property
    def cli_command(self) -> str:
        return "gemini"

    @property
    def install_hint(self) -> str:
        return "https://github.com/google/gemini-cli"

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]:
        """Return subprocess argv for a Gemini CLI session with *skill_name*."""
        cmd = [self.cli_command, "-i", f"Use the {skill_name} skill."]
        if model is not None:
            cmd.extend(["--model", model])
        return cmd

    def sync_skills(self) -> None:
        """Symlink bundled skills into Gemini CLI's discovery directory."""
        from prothon.skills import sync_skills

        sync_skills(target=Path.home() / ".gemini" / "skills")

    def env_overrides(self) -> dict[str, str]:
        """Return extra environment variables for Gemini CLI sessions."""
        return {}

    def subagent_type_map(self) -> dict[str, str]:
        """Return mapping from canonical subagent types to Gemini CLI names."""
        return {
            "general-purpose": "generalist",
            "explore": "codebase_investigator",
            "plan": "generalist",
        }


_BACKENDS: dict[str, type[AssistantBackend]] = {
    "claude-code": ClaudeCodeBackend,
    "opencode": OpenCodeBackend,
    "gemini-cli": GeminiCLIBackend,
}


def register_backend(name: str, cls: type) -> None:
    """Register a backend class under *name* for programmatic extension."""
    _BACKENDS[name] = cls


def get_backend(name: str = "claude-code") -> AssistantBackend:
    """Return a backend instance for *name*, or raise UnknownBackendError."""
    cls = _BACKENDS.get(name)
    if cls is None:
        registered = ", ".join(sorted(_BACKENDS.keys()))
        raise UnknownBackendError(
            f"no backend registered for '{name}' (available: {registered})"
        )
    return cls()


def launch(
    backend: AssistantBackend, skill_name: str, cwd: Path, model: str | None = None
) -> int:
    """Check binary, sync skills, run the assistant, and return exit code."""
    if not shutil.which(backend.cli_command):
        raise AssistantNotFoundError(
            f"{backend.name} ({backend.cli_command}) not found on PATH. "
            f"Install: {backend.install_hint}"
        )
    try:
        backend.sync_skills()
    except (IOError, OSError) as exc:
        raise ProthonError(f"failed to sync skills for {backend.name}: {exc}") from exc
    env = {**os.environ, **backend.env_overrides()}
    try:
        if model is None:
            cmd = backend.build_command(skill_name, cwd)
        else:
            cmd = backend.build_command(skill_name, cwd, model=model)
        return subprocess.run(cmd, cwd=cwd, env=env).returncode
    except OSError as exc:
        raise ProthonError(f"failed to launch {backend.name}: {exc}") from exc
