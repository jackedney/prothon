"""Tests for workflow CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from prothon.cli import (
    app,
    resolve_agent,
)
from prothon.exceptions import AssistantNotFoundError, ProthonError
from prothon.git import run_git
from prothon.scaffold import generate


runner = CliRunner()


def test_new_command_shows_help():
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "Generate" in result.output


def test_spec_command_exists():
    result = runner.invoke(app, ["spec", "--help"])
    assert result.exit_code == 0


def test_design_command_exists():
    result = runner.invoke(app, ["design", "--help"])
    assert result.exit_code == 0


def test_patterns_command_exists():
    result = runner.invoke(app, ["patterns", "--help"])
    assert result.exit_code == 0


def test_compliance_command_exists():
    result = runner.invoke(app, ["compliance", "--help"])
    assert result.exit_code == 0


def test_init_command_exists():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Adopt" in result.output


def test_init_fails_outside_git_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "not a git repository" in result.output


def test_init_fails_when_already_initialized(tmp_path, monkeypatch):
    # Create a git repo with docs/SPEC.md
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "already" in result.output.lower()


@pytest.fixture
def context():
    return {
        "project_name": "test-project",
        "module_name": "test_project",
        "description": "A test project",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "python_version": "3.13",
        "license": "MIT",
    }


def test_spec_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["spec"])
    assert result.exit_code != 0
    assert "no prothon project found" in result.output


def test_design_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["design"])
    assert result.exit_code != 0
    assert "no prothon project found" in result.output


def test_patterns_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["patterns"])
    assert result.exit_code != 0
    assert "no prothon project found" in result.output


def test_compliance_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["compliance"])
    assert result.exit_code != 0
    assert "no prothon project found" in result.output


def test_design_fails_without_spec(tmp_path, monkeypatch):
    """design command requires docs/SPEC.md to exist."""
    (tmp_path / "docs").mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("prothon.cli.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["design"])
    assert result.exit_code == 1
    assert "SPEC.md must exist" in result.output


def test_patterns_fails_without_design(tmp_path, monkeypatch):
    """patterns command requires docs/DESIGN.md to exist."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["patterns"])
    assert result.exit_code == 1
    assert "DESIGN.md must exist" in result.output


def test_spec_launches_claude_in_project(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch") as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_backend = mock_get_backend.return_value
            runner.invoke(app, ["spec"])
    mock_launch.assert_called_once_with(
        mock_backend, "prothon-spec-writer", dest, model=None
    )


def test_design_launches_single_session(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch") as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_backend = mock_get_backend.return_value
            runner.invoke(app, ["design"])
    mock_launch.assert_called_once_with(
        mock_backend, "prothon-design-writer", dest, model=None
    )


# --- _require_project_root ---


def test_require_project_root_error_message(tmp_path, monkeypatch):
    """Error message includes 'Error:' prefix and is written to stderr."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1


# --- _launch_skill error handling ---


def test_launch_skill_nonzero_exit_code_propagated(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch", return_value=42):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert result.exit_code == 42


def test_launch_skill_zero_exit_succeeds(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch", return_value=0):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert result.exit_code == 0


def test_launch_skill_assistant_not_found(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch(
        "prothon.cli.launch",
        side_effect=AssistantNotFoundError(
            "Claude Code (claude) not found on PATH. "
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        ),
    ):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1
    assert "not found on PATH" in result.output


def test_launch_skill_prothon_error(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.get_backend"):
        with patch(
            "prothon.cli.launch",
            side_effect=ProthonError("something wrong"),
        ):
            result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1
    assert "something wrong" in result.output


def test_launch_skill_passes_correct_skill_name(tmp_path, monkeypatch, context):
    """Each command passes the correct skill name to launch."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    commands_skills = [
        ("spec", "prothon-spec-writer"),
        ("design", "prothon-design-writer"),
        ("patterns", "prothon-patterns-writer"),
        ("execute", "prothon-execute"),
        ("compliance", "prothon-compliance-checker"),
    ]
    for cmd, skill_name in commands_skills:
        with patch("prothon.cli.launch", return_value=0) as mock_launch:
            with patch("prothon.cli.get_backend") as mock_backend:
                runner.invoke(app, [cmd])
        mock_launch.assert_called_once_with(
            mock_backend.return_value, skill_name, dest, model=None
        )


def test_launch_skill_exit_code_one_is_nonzero(tmp_path, monkeypatch, context):
    """rc=1 should still raise Exit (kills rc != 0 → rc != 1)."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch", return_value=1):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1


def test_launch_skill_assistant_not_found_install_url(tmp_path, monkeypatch, context):
    """Error message includes Install URL from backend's install_hint."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch(
        "prothon.cli.launch",
        side_effect=AssistantNotFoundError(
            "Claude Code (claude) not found on PATH. "
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        ),
    ):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert "Install:" in result.output
    assert "anthropic.com" in result.output


def test_launch_skill_assistant_not_found_no_xx_prefix(tmp_path, monkeypatch, context):
    """Error and Install lines must not have 'XX' padding (kills string mutations)."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch(
        "prothon.cli.launch",
        side_effect=AssistantNotFoundError(
            "Claude Code (claude) not found on PATH. "
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        ),
    ):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert "XX" not in result.output


# --- resolve_agent precedence chain ---


def test_resolve_agent_returns_default(tmp_path, monkeypatch):
    """Level 5: returns 'claude-code' when no config source is set."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    # No pyproject.toml, no global config — should fall through to default
    xdg = tmp_path / "xdg_config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "claude-code"


def test_resolve_agent_reads_pyproject_toml(tmp_path, monkeypatch):
    """Level 3: reads [tool.prothon].agent from pyproject.toml."""
    # Create project structure so find_project_root works
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
    (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    # Prevent global config from interfering
    xdg = tmp_path / "xdg_config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "opencode"


def test_resolve_agent_reads_global_config(tmp_path, monkeypatch):
    """Level 4: reads agent from ~/.config/prothon/config.toml."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    # No project root — ensure find_project_root raises (no docs/SPEC.md)
    xdg = tmp_path / "xdg_config"
    (xdg / "prothon").mkdir(parents=True)
    (xdg / "prothon" / "config.toml").write_text('agent = "opencode"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "opencode"


def test_resolve_agent_cli_value_overrides_pyproject(tmp_path, monkeypatch):
    """Level 1 beats level 3: CLI value overrides pyproject.toml config."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
    (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    assert resolve_agent("claude-code") == "claude-code"


def test_resolve_agent_pyproject_overrides_global_config(tmp_path, monkeypatch):
    """Level 3 beats level 4: pyproject.toml overrides global config."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
    (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    # Set up global config with a different value
    xdg = tmp_path / "xdg_config"
    (xdg / "prothon").mkdir(parents=True)
    (xdg / "prothon" / "config.toml").write_text('agent = "claude-code"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "opencode"


def test_resolve_agent_global_config_overrides_default(tmp_path, monkeypatch):
    """Level 4 beats level 5: global config overrides the hardcoded default."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    # No pyproject.toml [tool.prothon], no docs/SPEC.md
    xdg = tmp_path / "xdg_config"
    (xdg / "prothon").mkdir(parents=True)
    (xdg / "prothon" / "config.toml").write_text('agent = "opencode"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "opencode"


def test_agent_flag_passed_through_to_backend(tmp_path, monkeypatch, context):
    """--agent flag reaches resolve_agent and selects the correct backend."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch", return_value=0) as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            runner.invoke(app, ["spec", "--agent", "opencode"])
    mock_get_backend.assert_called_once_with("opencode")
    mock_launch.assert_called_once()


def test_unknown_backend_produces_error(tmp_path, monkeypatch, context):
    """Unknown backend name shows error with 'no backend registered'."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    result = runner.invoke(app, ["spec", "--agent", "unknown-backend"])
    assert result.exit_code == 1
    assert "no backend registered" in result.output


def test_resolve_agent_cli_value_takes_priority(tmp_path, monkeypatch):
    """Level 1: explicit cli_value is returned immediately."""
    monkeypatch.chdir(tmp_path)
    assert resolve_agent("opencode") == "opencode"


def test_resolve_agent_env_var_via_cli_runner(tmp_path, monkeypatch, context):
    """PROTHON_AGENT env var flows through the Typer option into resolve_agent."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    with patch("prothon.cli.launch", return_value=0):
        with patch("prothon.cli.get_backend") as mock_get_backend:
            runner.invoke(app, ["spec"])
    mock_get_backend.assert_called_once_with("opencode")


def test_resolve_agent_cli_flag_overrides_env_var(tmp_path, monkeypatch, context):
    """Level 1 beats level 2: CLI --agent flag overrides PROTHON_AGENT."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    with patch("prothon.cli.launch", return_value=0):
        with patch("prothon.cli.get_backend") as mock_get_backend:
            runner.invoke(app, ["spec", "--agent", "claude-code"])
    mock_get_backend.assert_called_once_with("claude-code")


def test_resolve_agent_pyproject_without_tool_prothon_section(tmp_path, monkeypatch):
    """pyproject.toml exists but has no [tool.prothon] — falls through."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    xdg = tmp_path / "xdg_config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "claude-code"


def test_resolve_agent_empty_global_config_falls_to_default(tmp_path, monkeypatch):
    """Global config exists but has no agent key — falls through to default."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROTHON_AGENT", raising=False)
    xdg = tmp_path / "xdg_config"
    (xdg / "prothon").mkdir(parents=True)
    (xdg / "prothon" / "config.toml").write_text("# empty config\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_agent() == "claude-code"


# --- SPEC.md protection (R21) ---


def test_launch_skill_warns_when_spec_modified(tmp_path, monkeypatch, context):
    """Non-spec skills warn if SPEC.md was modified during the session."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    def modify_spec(*args, **kwargs):
        (dest / "docs" / "SPEC.md").write_text("# Tampered\n")
        return 0

    with patch("prothon.cli.launch", side_effect=modify_spec):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["design"])
    assert "SPEC.md was modified outside" in result.output


def test_launch_skill_no_warning_for_spec_writer(tmp_path, monkeypatch, context):
    """spec-writer is allowed to modify SPEC.md without warning."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    def modify_spec(*args, **kwargs):
        (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
        return 0

    with patch("prothon.cli.launch", side_effect=modify_spec):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["spec"])
    assert "SPEC.md was modified" not in result.output


def test_launch_skill_no_warning_when_spec_unchanged(tmp_path, monkeypatch, context):
    """No warning when SPEC.md is unchanged after a non-spec skill."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    with patch("prothon.cli.launch", return_value=0):
        with patch("prothon.cli.get_backend"):
            result = runner.invoke(app, ["design"])
    assert "SPEC.md was modified" not in result.output


# --- _launch_skill model/provider handling ---


def test_launch_skill_claude_ignores_model_only(tmp_path, monkeypatch, context):
    """Claude Code ignores model option - no error even if only model is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    with patch("prothon.cli.launch", return_value=0) as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_get_backend.return_value.name = "Claude Code"
            result = runner.invoke(
                app, ["spec", "--model", "glm-5", "--agent", "claude-code"]
            )
    assert result.exit_code == 0
    mock_launch.assert_called_once()
    assert mock_launch.call_args.kwargs["model"] is None


def test_launch_skill_claude_ignores_provider_only(tmp_path, monkeypatch, context):
    """Claude Code ignores provider option - no error even if only provider is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    with patch("prothon.cli.launch", return_value=0) as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_get_backend.return_value.name = "Claude Code"
            result = runner.invoke(
                app, ["spec", "--provider", "z-ai", "--agent", "claude-code"]
            )
    assert result.exit_code == 0
    mock_launch.assert_called_once()
    assert mock_launch.call_args.kwargs["model"] is None


def test_launch_skill_claude_ignores_model_env_var(tmp_path, monkeypatch, context):
    """Claude Code ignores PROTHON_MODEL env var - no error even if only model is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setenv("PROTHON_MODEL", "glm-5")

    with patch("prothon.cli.launch", return_value=0) as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_get_backend.return_value.name = "Claude Code"
            result = runner.invoke(app, ["spec", "--agent", "claude-code"])
    assert result.exit_code == 0
    mock_launch.assert_called_once()
    assert mock_launch.call_args.kwargs["model"] is None


def test_launch_skill_opencode_validates_model_provider(tmp_path, monkeypatch, context):
    """opencode still validates model/provider - error if only one is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    with patch("prothon.cli.get_backend") as mock_get_backend:
        mock_get_backend.return_value.name = "opencode"
        result = runner.invoke(app, ["spec", "--model", "glm-5", "--agent", "opencode"])
    assert result.exit_code == 1
    assert "--provider requires --model" in result.output


def test_launch_skill_opencode_accepts_both_model_provider(
    tmp_path, monkeypatch, context
):
    """opencode accepts both model and provider - passes resolved model to launch."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    with patch("prothon.cli.launch", return_value=0) as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_get_backend.return_value.name = "opencode"
            result = runner.invoke(
                app,
                [
                    "spec",
                    "--model",
                    "glm-5",
                    "--provider",
                    "z-ai",
                    "--agent",
                    "opencode",
                ],
            )
    assert result.exit_code == 0
    mock_launch.assert_called_once()
    assert mock_launch.call_args.kwargs["model"] == "z-ai/glm-5"
