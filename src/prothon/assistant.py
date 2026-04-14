"""Abstract assistant interface, backend registry, and launch lifecycle."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

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


@dataclass(frozen=True)
class BackendConfig:
    name: str
    cli_command: str
    install_hint: str
    skills_target: str
    subagent_map: Mapping[str, str]
    prompt_builder: str


_CONFIGS: dict[str, BackendConfig] = {
    "claude-code": BackendConfig(
        name="Claude Code",
        cli_command="claude",
        install_hint="https://docs.anthropic.com/en/docs/claude-code",
        skills_target=".claude/skills",
        subagent_map={
            "general-purpose": "general-purpose",
            "explore": "Explore",
            "plan": "Plan",
        },
        prompt_builder="slash",
    ),
    "opencode": BackendConfig(
        name="opencode",
        cli_command="opencode",
        install_hint="https://opencode.ai",
        skills_target="opencode/skills",
        subagent_map={
            "general-purpose": "general",
            "explore": "explore",
            "plan": "plan",
        },
        prompt_builder="flag",
    ),
    "gemini": BackendConfig(
        name="Gemini CLI",
        cli_command="gemini",
        install_hint="https://github.com/google/gemini-cli",
        skills_target=".gemini/skills",
        subagent_map={
            "general-purpose": "generalist_agent",
            "explore": "codebase_investigator",
            "plan": "generalist_agent",
        },
        prompt_builder="yolo",
    ),
}


class _GenericBackend:
    """Data-driven backend that delegates all behaviour to a BackendConfig."""

    def __init__(self, config: BackendConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def cli_command(self) -> str:
        return self._config.cli_command

    @property
    def install_hint(self) -> str:
        return self._config.install_hint

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]:
        cfg = self._config
        if cfg.prompt_builder == "slash":
            return [
                cfg.cli_command,
                "--dangerously-skip-permissions",
                f"/{skill_name}",
            ]
        if cfg.prompt_builder == "flag":
            cmd = [cfg.cli_command, "--prompt", f"/{skill_name}"]
            if model is not None:
                cmd.extend(["--model", model])
            return cmd
        if cfg.prompt_builder == "yolo":
            prompt = f"Activate the {skill_name} skill and follow its instructions."
            cmd = [cfg.cli_command, "--approval-mode=yolo", prompt]
            if model is not None:
                cmd.extend(["--model", model])
            return cmd
        msg = f"Unknown prompt_builder: {cfg.prompt_builder!r}"
        raise ValueError(msg)

    def sync_skills(self) -> None:
        from prothon.fs import xdg_config_home
        from prothon.skills import sync_skills

        cfg = self._config
        if cfg.skills_target.startswith("."):
            target = Path.home() / cfg.skills_target
        else:
            target = xdg_config_home() / cfg.skills_target
        sync_skills(target=target)

    def env_overrides(self) -> dict[str, str]:
        return {}

    def subagent_type_map(self) -> dict[str, str]:
        return dict(self._config.subagent_map)


class ClaudeCodeBackend(_GenericBackend):
    def __init__(self) -> None:
        super().__init__(_CONFIGS["claude-code"])


class OpenCodeBackend(_GenericBackend):
    def __init__(self) -> None:
        super().__init__(_CONFIGS["opencode"])


class GeminiCLIBackend(_GenericBackend):
    def __init__(self) -> None:
        super().__init__(_CONFIGS["gemini"])


_BACKENDS: dict[str, type[AssistantBackend]] = {
    "claude-code": ClaudeCodeBackend,
    "opencode": OpenCodeBackend,
    "gemini": GeminiCLIBackend,
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
    except OSError as exc:
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
