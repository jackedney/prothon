"""Tests for assistant backend protocol, registry, and launch lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prothon.assistant import (
    AssistantBackend,
    ClaudeCodeBackend,
    OpenCodeBackend,
    get_backend,
    launch,
    register_backend,
)
from prothon.exceptions import AssistantNotFoundError, UnknownBackendError


class FakeBackend:
    """Minimal backend that satisfies AssistantBackend structurally."""

    @property
    def name(self) -> str:
        return "Fake"

    @property
    def cli_command(self) -> str:
        return "fake-assistant"

    @property
    def install_hint(self) -> str:
        return "https://example.com/install"

    def build_command(self, skill_name: str, cwd: Path) -> list[str]:
        return [self.cli_command, f"/{skill_name}"]

    def sync_skills(self) -> None:
        pass

    def env_overrides(self) -> dict[str, str]:
        return {}


# --- Protocol conformance ---


def test_fake_backend_satisfies_protocol() -> None:
    """FakeBackend structurally satisfies AssistantBackend."""
    backend: AssistantBackend = FakeBackend()
    assert backend.name == "Fake"
    assert backend.cli_command == "fake-assistant"
    assert backend.install_hint == "https://example.com/install"
    assert backend.build_command("my-skill", Path("/tmp")) == [
        "fake-assistant",
        "/my-skill",
    ]
    assert backend.env_overrides() == {}


# --- Registry ---


def test_get_backend_returns_claude_code() -> None:
    """get_backend('claude-code') returns a ClaudeCodeBackend instance."""
    backend = get_backend("claude-code")
    assert isinstance(backend, ClaudeCodeBackend)


def test_get_backend_returns_opencode() -> None:
    """get_backend('opencode') returns an OpenCodeBackend instance."""
    backend = get_backend("opencode")
    assert isinstance(backend, OpenCodeBackend)


def test_get_backend_default_is_claude_code() -> None:
    """get_backend() defaults to claude-code."""
    backend = get_backend()
    assert isinstance(backend, ClaudeCodeBackend)


def test_get_backend_unknown_raises() -> None:
    """get_backend with an unknown name raises UnknownBackendError."""
    with pytest.raises(
        UnknownBackendError, match="no backend registered for 'unknown'"
    ):
        get_backend("unknown")


def test_register_backend_adds_to_registry() -> None:
    """register_backend makes a new backend available via get_backend."""
    register_backend("fake-test", FakeBackend)
    backend = get_backend("fake-test")
    assert isinstance(backend, FakeBackend)


# --- ClaudeCodeBackend ---


def test_claude_code_backend_properties() -> None:
    """ClaudeCodeBackend exposes correct name, cli_command, and install_hint."""
    backend = ClaudeCodeBackend()
    assert backend.name == "Claude Code"
    assert backend.cli_command == "claude"
    assert backend.install_hint == "https://docs.anthropic.com/en/docs/claude-code"


def test_claude_code_backend_build_command() -> None:
    """build_command constructs the expected argv."""
    backend = ClaudeCodeBackend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"))
    assert result == [
        "claude",
        "--dangerously-skip-permissions",
        "/prothon-spec-writer",
    ]


def test_claude_code_backend_env_overrides() -> None:
    """ClaudeCodeBackend returns empty env_overrides."""
    backend = ClaudeCodeBackend()
    assert backend.env_overrides() == {}


# --- OpenCodeBackend ---


def test_opencode_backend_properties() -> None:
    """OpenCodeBackend exposes correct name, cli_command, and install_hint."""
    backend = OpenCodeBackend()
    assert backend.name == "opencode"
    assert backend.cli_command == "opencode"
    assert backend.install_hint == "https://opencode.ai"


def test_opencode_backend_build_command() -> None:
    """build_command constructs the expected argv."""
    backend = OpenCodeBackend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"))
    assert result == ["opencode", "/prothon-spec-writer"]


def test_opencode_backend_env_overrides() -> None:
    """OpenCodeBackend returns empty env_overrides."""
    backend = OpenCodeBackend()
    assert backend.env_overrides() == {}


# --- launch lifecycle ---


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_with_fake_backend(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() checks binary, syncs skills, runs subprocess, returns exit code."""
    mock_run.return_value = MagicMock(returncode=0)
    backend = FakeBackend()
    expected_env = {**os.environ, **backend.env_overrides()}

    code = launch(backend, "my-skill", cwd=tmp_path)

    mock_which.assert_called_once_with("fake-assistant")
    mock_run.assert_called_once_with(
        ["fake-assistant", "/my-skill"],
        cwd=tmp_path,
        env=expected_env,
    )
    assert code == 0


@patch("prothon.assistant.shutil.which", return_value=None)
def test_launch_raises_when_binary_not_found(
    mock_which: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() raises AssistantNotFoundError when the binary is missing."""
    backend = FakeBackend()

    with pytest.raises(AssistantNotFoundError, match="Fake.*fake-assistant.*not found"):
        launch(backend, "my-skill", cwd=tmp_path)


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_returns_nonzero_exit_code(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() propagates a non-zero exit code from the subprocess."""
    mock_run.return_value = MagicMock(returncode=1)
    backend = FakeBackend()

    code = launch(backend, "my-skill", cwd=tmp_path)

    assert code == 1
