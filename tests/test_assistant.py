"""Tests for assistant backend protocol, registry, and launch lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from prothon.assistant import (
    _BACKENDS,
    AssistantBackend,
    ClaudeCodeBackend,
    GeminiCLIBackend,
    OpenCodeBackend,
    OB1Backend,
    get_backend,
    launch,
    register_backend,
)
from prothon.exceptions import AssistantNotFoundError, ProthonError, UnknownBackendError


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

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]:
        return [self.cli_command, f"/{skill_name}"]

    def sync_skills(self) -> None:
        pass

    def env_overrides(self) -> dict[str, str]:
        return {}

    def subagent_type_map(self) -> dict[str, str]:
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
    previous = _BACKENDS.get("fake-test")
    register_backend("fake-test", FakeBackend)
    try:
        backend = get_backend("fake-test")
        assert isinstance(backend, FakeBackend)
    finally:
        if previous is None:
            _BACKENDS.pop("fake-test", None)
        else:
            _BACKENDS["fake-test"] = previous


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


@pytest.mark.parametrize(
    "backend_cls",
    [ClaudeCodeBackend, OpenCodeBackend, GeminiCLIBackend, OB1Backend],
)
def test_backend_env_overrides_empty(backend_cls) -> None:
    """All backends return empty env_overrides."""
    assert backend_cls().env_overrides() == {}


def test_claude_code_backend_subagent_type_map() -> None:
    """ClaudeCodeBackend returns Claude Code subagent type mappings."""
    backend = ClaudeCodeBackend()
    expected = {
        "general-purpose": "general-purpose",
        "explore": "Explore",
        "plan": "Plan",
    }
    assert backend.subagent_type_map() == expected


# --- OpenCodeBackend ---


def test_opencode_backend_properties() -> None:
    """OpenCodeBackend exposes correct name, cli_command, and install_hint."""
    backend = OpenCodeBackend()
    assert backend.name == "opencode"
    assert backend.cli_command == "opencode"
    assert backend.install_hint == "https://opencode.ai"


def test_opencode_backend_build_command() -> None:
    """build_command constructs the expected argv for interactive TUI mode."""
    backend = OpenCodeBackend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"))
    assert result == ["opencode", "--prompt", "/prothon-spec-writer"]


def test_opencode_backend_build_command_uses_slash_prefix() -> None:
    """build_command prefixes skill name with '/' so opencode treats it as a command."""
    backend = OpenCodeBackend()
    cmd = backend.build_command("prothon-patterns-writer", Path("/tmp"))
    assert cmd[-1] == "/prothon-patterns-writer"


def test_opencode_backend_subagent_type_map() -> None:
    """OpenCodeBackend returns opencode subagent type mappings."""
    backend = OpenCodeBackend()
    expected = {"general-purpose": "general", "explore": "explore", "plan": "plan"}
    assert backend.subagent_type_map() == expected


def test_opencode_backend_build_command_with_model() -> None:
    """build_command appends --model provider/model when model is provided."""
    backend = OpenCodeBackend()
    result = backend.build_command(
        "prothon-spec-writer", Path("/tmp"), model="z-ai/glm-5"
    )
    assert result == [
        "opencode",
        "--prompt",
        "/prothon-spec-writer",
        "--model",
        "z-ai/glm-5",
    ]


def test_opencode_backend_build_command_without_model() -> None:
    """build_command does not include --model when model is None."""
    backend = OpenCodeBackend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"), model=None)
    assert result == ["opencode", "--prompt", "/prothon-spec-writer"]
    assert "--model" not in result


def test_get_backend_returns_gemini() -> None:
    """get_backend('gemini') returns a GeminiCLIBackend instance."""
    backend = get_backend("gemini")
    assert isinstance(backend, GeminiCLIBackend)


# --- GeminiCLIBackend ---


def test_gemini_cli_backend_properties() -> None:
    """GeminiCLIBackend exposes correct name, cli_command, and install_hint."""
    from prothon.assistant import GeminiCLIBackend

    backend = GeminiCLIBackend()
    assert backend.name == "Gemini CLI"
    assert backend.cli_command == "gemini"
    assert backend.install_hint == "https://github.com/google/gemini-cli"


def test_gemini_cli_backend_build_command() -> None:
    """build_command constructs the expected argv."""
    from prothon.assistant import GeminiCLIBackend

    backend = GeminiCLIBackend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"))
    prompt = "Activate the prothon-spec-writer skill and follow its instructions."
    assert result == ["gemini", "--approval-mode=yolo", prompt]


def test_gemini_cli_backend_build_command_with_model() -> None:
    """build_command constructs the expected argv with a model specified."""
    from prothon.assistant import GeminiCLIBackend

    backend = GeminiCLIBackend()
    result = backend.build_command(
        "prothon-spec-writer", Path("/tmp"), model="gemini-2.0-flash"
    )
    prompt = "Activate the prothon-spec-writer skill and follow its instructions."
    assert result == [
        "gemini",
        "--approval-mode=yolo",
        prompt,
        "--model",
        "gemini-2.0-flash",
    ]


def test_gemini_cli_backend_subagent_type_map() -> None:
    """GeminiCLIBackend returns Gemini CLI subagent type mappings."""
    from prothon.assistant import GeminiCLIBackend

    backend = GeminiCLIBackend()
    expected = {
        "general-purpose": "generalist_agent",
        "explore": "codebase_investigator",
        "plan": "generalist_agent",
    }
    assert backend.subagent_type_map() == expected


@patch("prothon.skills.sync_skills")
def test_gemini_cli_sync_skills_calls_with_home_gemini_skills(
    mock_sync: MagicMock,
) -> None:
    """GeminiCLIBackend.sync_skills() targets ~/.gemini/skills/."""
    from prothon.assistant import GeminiCLIBackend

    backend = GeminiCLIBackend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(target=Path.home() / ".gemini" / "skills")


# --- OB1Backend ---


def test_ob1_backend_properties() -> None:
    """OB1Backend exposes correct name, cli_command, and install_hint."""
    from prothon.assistant import OB1Backend

    backend = OB1Backend()
    assert backend.name == "OB1"
    assert backend.cli_command == "ob1"
    assert backend.install_hint == "https://www.openblocklabs.com/manual"


def test_ob1_backend_build_command() -> None:
    """build_command constructs the expected argv."""
    from prothon.assistant import OB1Backend

    backend = OB1Backend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"))
    assert result == ["ob1", "Use the prothon-spec-writer skill."]


def test_ob1_backend_build_command_with_model() -> None:
    """build_command constructs the expected argv with a model specified."""
    from prothon.assistant import OB1Backend

    backend = OB1Backend()
    result = backend.build_command("prothon-spec-writer", Path("/tmp"), model="gpt-4o")
    assert result == ["ob1", "Use the prothon-spec-writer skill.", "--model", "gpt-4o"]


def test_ob1_backend_subagent_type_map() -> None:
    """OB1Backend returns OB1 subagent type mappings."""
    from prothon.assistant import OB1Backend

    backend = OB1Backend()
    expected = {
        "general-purpose": "general",
        "explore": "explore",
        "plan": "plan",
    }
    assert backend.subagent_type_map() == expected


@patch("prothon.skills.sync_skills")
def test_ob1_sync_skills_calls_with_home_ob1_skills(
    mock_sync: MagicMock,
) -> None:
    """OB1Backend.sync_skills() targets ~/.ob1/skills/."""
    from prothon.assistant import OB1Backend

    backend = OB1Backend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(target=Path.home() / ".ob1" / "skills")


def test_get_backend_returns_ob1() -> None:
    """get_backend('ob1') returns an OB1Backend instance."""
    backend = get_backend("ob1")
    assert isinstance(backend, OB1Backend)


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


# --- Backend sync_skills ---


@patch("prothon.skills.sync_skills")
def test_claude_code_sync_skills_calls_with_home_claude_skills(
    mock_sync: MagicMock,
) -> None:
    """ClaudeCodeBackend.sync_skills() targets ~/.claude/skills/."""
    backend = ClaudeCodeBackend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(target=Path.home() / ".claude" / "skills")


@patch("prothon.skills.sync_skills")
def test_opencode_sync_skills_calls_with_xdg_default(
    mock_sync: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCodeBackend.sync_skills() defaults to ~/.config/opencode/skills/."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    backend = OpenCodeBackend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(
        target=Path.home() / ".config" / "opencode" / "skills"
    )


@patch("prothon.skills.sync_skills")
def test_opencode_sync_skills_respects_xdg_config_home(
    mock_sync: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCodeBackend.sync_skills() uses XDG_CONFIG_HOME when set."""
    monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
    backend = OpenCodeBackend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(
        target=Path("/custom/config") / "opencode" / "skills"
    )


@patch("prothon.skills.sync_skills")
def test_opencode_sync_skills_ignores_relative_xdg_config_home(
    mock_sync: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCodeBackend.sync_skills() falls back to ~/.config
    when XDG_CONFIG_HOME is relative.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
    backend = OpenCodeBackend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(
        target=Path.home() / ".config" / "opencode" / "skills"
    )


@patch("prothon.skills.sync_skills")
def test_opencode_sync_skills_ignores_empty_xdg_config_home(
    mock_sync: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCodeBackend.sync_skills() falls back to ~/.config
    when XDG_CONFIG_HOME is empty.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    backend = OpenCodeBackend()
    backend.sync_skills()

    mock_sync.assert_called_once_with(
        target=Path.home() / ".config" / "opencode" / "skills"
    )


# --- Launch lifecycle verification ---


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_calls_sync_skills_on_backend(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() calls sync_skills() on the backend during the lifecycle."""
    mock_run.return_value = MagicMock(returncode=0)
    backend = FakeBackend()

    with patch.object(backend, "sync_skills") as mock_sync:
        launch(backend, "my-skill", cwd=tmp_path)

    mock_sync.assert_called_once()


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_merges_env_overrides_into_subprocess_env(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() merges env_overrides into the subprocess environment."""
    mock_run.return_value = MagicMock(returncode=0)

    class EnvBackend(FakeBackend):
        def env_overrides(self) -> dict[str, str]:
            return {"CUSTOM_VAR": "custom_value"}

    backend = EnvBackend()
    launch(backend, "my-skill", cwd=tmp_path)

    call_env = mock_run.call_args.kwargs["env"]
    assert call_env["CUSTOM_VAR"] == "custom_value"


@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_wraps_sync_skills_os_error(
    mock_which: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() wraps OSError from sync_skills() in ProthonError."""

    class FailingSyncBackend(FakeBackend):
        def sync_skills(self) -> None:
            raise OSError("permission denied")

    backend = FailingSyncBackend()
    with pytest.raises(ProthonError, match="failed to sync skills for Fake"):
        launch(backend, "my-skill", cwd=tmp_path)


def test_get_backend_unknown_error_lists_registered_backends() -> None:
    """UnknownBackendError message lists all registered backend names."""
    with pytest.raises(UnknownBackendError) as exc_info:
        get_backend("nonexistent")

    msg = str(exc_info.value)
    assert "claude-code" in msg
    assert "opencode" in msg


# --- Backwards compatibility for build_command signature ---


class LegacyBackend:
    """Backend with old signature (no model parameter)."""

    @property
    def name(self) -> str:
        return "Legacy"

    @property
    def cli_command(self) -> str:
        return "legacy-assistant"

    @property
    def install_hint(self) -> str:
        return "https://example.com/legacy"

    def build_command(self, skill_name: str, cwd: Path) -> list[str]:
        return [self.cli_command, f"/{skill_name}"]

    def sync_skills(self) -> None:
        pass

    def env_overrides(self) -> dict[str, str]:
        return {}


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/legacy-assistant")
def test_launch_with_legacy_backend_when_model_is_none(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() works with a backend that doesn't accept model parameter
    when model is None.
    """
    mock_run.return_value = MagicMock(returncode=0)
    backend = LegacyBackend()

    code = launch(backend, "my-skill", cwd=tmp_path, model=None)  # type: ignore[arg-type]

    mock_run.assert_called_once_with(
        ["legacy-assistant", "/my-skill"],
        cwd=tmp_path,
        env=os.environ,
    )
    assert code == 0


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_calls_build_command_without_model_when_none(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() calls build_command(skill_name, cwd) when model is None."""
    mock_run.return_value = MagicMock(returncode=0)
    backend = FakeBackend()

    with patch.object(
        backend, "build_command", wraps=backend.build_command
    ) as mock_build:
        launch(backend, "my-skill", cwd=tmp_path, model=None)

    mock_build.assert_called_once_with("my-skill", tmp_path)


@patch("prothon.assistant.subprocess.run")
@patch("prothon.assistant.shutil.which", return_value="/usr/bin/fake-assistant")
def test_launch_calls_build_command_with_model_when_provided(
    mock_which: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """launch() calls build_command(skill_name, cwd, model=model)
    when model is not None.
    """
    mock_run.return_value = MagicMock(returncode=0)
    backend = FakeBackend()

    with patch.object(
        backend, "build_command", wraps=backend.build_command
    ) as mock_build:
        launch(backend, "my-skill", cwd=tmp_path, model="z-ai/glm-5")

    mock_build.assert_called_once_with("my-skill", tmp_path, model="z-ai/glm-5")
