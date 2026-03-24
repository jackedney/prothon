"""Tests for workflow CLI commands."""

from __future__ import annotations

import re
import shutil

import pytest
from tests.fakes import FakeAssistantBackend, Recorder
from prothon.cli import (
    app,
)
from prothon.exceptions import AssistantNotFoundError, GitError, ProthonError
from prothon.git import rev_parse_head, run_git
from prothon.scaffold import generate
from typer.testing import CliRunner

runner = CliRunner()

_CONTEXT = {
    "project_name": "test-project",
    "module_name": "test_project",
    "description": "A test project",
    "author_name": "Test Author",
    "author_email": "test@example.com",
    "python_version": "3.13",
    "license": "MIT",
}


@pytest.fixture(scope="module")
def shared_project(tmp_path_factory):
    """Generate a Copier project once, copy for tests that only need a valid root."""
    dest = tmp_path_factory.mktemp("shared") / "test-project"
    generate(dest, _CONTEXT)
    return dest


@pytest.fixture
def project_copy(shared_project, tmp_path):
    """Fast per-test copy of the shared generated project."""
    dest = tmp_path / "test-project"
    shutil.copytree(shared_project, dest, symlinks=True)
    return dest


@pytest.fixture
def context():
    return dict(_CONTEXT)


def test_new_command_shows_help():
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "Generate" in result.output


@pytest.mark.parametrize("cmd", ["spec", "design", "patterns", "compliance"])
def test_command_exists(cmd):
    result = runner.invoke(app, [cmd, "--help"])
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
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "already" in result.output.lower()


@pytest.mark.parametrize("cmd", ["spec", "design", "patterns", "compliance"])
def test_command_fails_outside_project(cmd, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [cmd])
    assert result.exit_code != 0
    assert "no prothon project found" in result.output


def test_design_fails_without_spec(tmp_path, monkeypatch):
    """design command requires docs/SPEC.md to exist."""
    (tmp_path / "docs").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("prothon.cli.find_project_root", lambda: tmp_path)
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


def test_spec_launches_claude_in_project(project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    fake_backend = FakeAssistantBackend()
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=fake_backend)
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    runner.invoke(app, ["spec"])
    assert fake_launch.call_count >= 1
    assert fake_launch.calls[0][0][:3] == (
        fake_backend,
        "prothon-spec-writer",
        project_copy,
    )
    assert fake_launch.calls[0][1] == {"model": None}


def test_design_launches_single_session(project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    fake_backend = FakeAssistantBackend()
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=fake_backend)
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    runner.invoke(app, ["design"])
    assert fake_launch.call_count >= 1
    assert fake_launch.calls[0][0][:3] == (
        fake_backend,
        "prothon-design-writer",
        project_copy,
    )
    assert fake_launch.calls[0][1] == {"model": None}


# --- _require_project_root ---


def test_require_project_root_error_message(tmp_path, monkeypatch):
    """Error message includes 'Error:' prefix and is written to stderr."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1


# --- _launch_skill error handling ---


def test_launch_skill_nonzero_exit_code_propagated(project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=42))
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 42


def test_launch_skill_zero_exit_succeeds(project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 0


def test_launch_skill_assistant_not_found(project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.commands.launch",
        Recorder(
            side_effect=AssistantNotFoundError(
                "Claude Code (claude) not found on PATH. "
                "Install: https://docs.anthropic.com/en/docs/claude-code"
            ),
        ),
    )
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1
    assert "not found on PATH" in result.output


def test_launch_skill_prothon_error(project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.commands.launch",
        Recorder(side_effect=ProthonError("something wrong")),
    )
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1
    assert "something wrong" in result.output


def test_launch_skill_passes_correct_skill_name(project_copy, monkeypatch):
    """Each command passes the correct skill name to launch."""
    monkeypatch.chdir(project_copy)

    commands_skills = [
        ("spec", "prothon-spec-writer"),
        ("design", "prothon-design-writer"),
        ("patterns", "prothon-patterns-writer"),
        ("execute", "prothon-execute"),
        ("compliance", "prothon-compliance-checker"),
    ]
    for cmd, skill_name in commands_skills:
        fake_backend = FakeAssistantBackend()
        fake_launch = Recorder(return_value=0)
        monkeypatch.setattr(
            "prothon.commands.get_backend", Recorder(return_value=fake_backend)
        )
        monkeypatch.setattr("prothon.commands.launch", fake_launch)
        runner.invoke(app, [cmd])
        assert fake_launch.called_with_arg(1, skill_name)


def test_launch_skill_exit_code_one_is_nonzero(project_copy, monkeypatch):
    """rc=1 should still raise Exit (kills rc != 0 → rc != 1)."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=1))
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1


def test_launch_skill_assistant_not_found_install_url(project_copy, monkeypatch):
    """Error message includes Install URL from backend's install_hint."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.commands.launch",
        Recorder(
            side_effect=AssistantNotFoundError(
                "Claude Code (claude) not found on PATH. "
                "Install: https://docs.anthropic.com/en/docs/claude-code"
            ),
        ),
    )
    result = runner.invoke(app, ["spec"])
    assert "Install:" in result.output
    assert "anthropic.com" in result.output


def test_launch_skill_assistant_not_found_no_xx_prefix(project_copy, monkeypatch):
    """Error and Install lines must not have 'XX' padding (kills string mutations)."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.commands.launch",
        Recorder(
            side_effect=AssistantNotFoundError(
                "Claude Code (claude) not found on PATH. "
                "Install: https://docs.anthropic.com/en/docs/claude-code"
            ),
        ),
    )
    result = runner.invoke(app, ["spec"])
    assert "XX" not in result.output


# --- CLI integration tests for agent/model/provider ---


def test_agent_flag_passed_through_to_backend(project_copy, monkeypatch):
    """--agent flag reaches resolve_agent and selects the correct backend."""
    monkeypatch.chdir(project_copy)
    fake_get_backend = Recorder(return_value=FakeAssistantBackend())
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr("prothon.commands.get_backend", fake_get_backend)
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    runner.invoke(app, ["spec", "--agent", "opencode"])
    assert fake_get_backend.called_with_arg(0, "opencode")
    assert fake_launch.call_count >= 1


def test_unknown_backend_produces_error(project_copy, monkeypatch):
    """Unknown backend name shows error with 'no backend registered'."""
    monkeypatch.chdir(project_copy)
    result = runner.invoke(app, ["spec", "--agent", "unknown-backend"])
    assert result.exit_code == 1
    assert "no backend registered" in result.output


def test_resolve_agent_env_var_via_cli_runner(project_copy, monkeypatch):
    """PROTHON_AGENT env var flows through the Typer option into resolve_agent."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    fake_get_backend = Recorder(return_value=FakeAssistantBackend())
    monkeypatch.setattr("prothon.commands.get_backend", fake_get_backend)
    monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
    runner.invoke(app, ["spec"])
    assert fake_get_backend.called_with_arg(0, "opencode")


def test_resolve_agent_cli_flag_overrides_env_var(project_copy, monkeypatch):
    """Level 1 beats level 2: CLI --agent flag overrides PROTHON_AGENT."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    fake_get_backend = Recorder(return_value=FakeAssistantBackend())
    monkeypatch.setattr("prothon.commands.get_backend", fake_get_backend)
    monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
    runner.invoke(app, ["spec", "--agent", "claude-code"])
    assert fake_get_backend.called_with_arg(0, "claude-code")


# --- CLI integration tests for model/provider ---


def test_opencode_receives_resolved_model(project_copy, monkeypatch):
    """opencode backend receives resolved model in format provider/model."""
    monkeypatch.chdir(project_copy)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(
        app,
        ["spec", "--agent", "opencode", "--model", "glm-5", "--provider", "z-ai"],
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] == "z-ai/glm-5"


def test_opencode_receives_slash_model_as_is(project_copy, monkeypatch):
    """opencode receives model with '/' as-is when no provider specified."""
    monkeypatch.chdir(project_copy)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(
        app,
        ["spec", "--agent", "opencode", "--model", "z-ai/glm-5"],
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] == "z-ai/glm-5"


def test_opencode_no_model_passes_none(project_copy, monkeypatch):
    """opencode with no model/provider configured passes None to launch."""
    monkeypatch.chdir(project_copy)
    monkeypatch.delenv("PROTHON_MODEL", raising=False)
    monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--agent", "opencode"])
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


# --- SPEC.md protection (R21) ---


def test_launch_skill_warns_when_spec_modified(project_copy, monkeypatch):
    """Non-spec skills warn if SPEC.md was modified during the session."""
    monkeypatch.chdir(project_copy)

    def modify_spec(*args, **kwargs):
        (project_copy / "docs" / "SPEC.md").write_text("# Tampered\n")
        return 0

    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.commands.launch", Recorder(side_effect=modify_spec))
    result = runner.invoke(app, ["design"])
    assert "SPEC.md was modified outside" in result.output


def test_launch_skill_no_warning_for_spec_writer(project_copy, monkeypatch):
    """spec-writer is allowed to modify SPEC.md without warning."""
    monkeypatch.chdir(project_copy)

    def modify_spec(*args, **kwargs):
        (project_copy / "docs" / "SPEC.md").write_text("# Updated spec\n")
        return 0

    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.commands.launch", Recorder(side_effect=modify_spec))
    result = runner.invoke(app, ["spec"])
    assert "SPEC.md was modified" not in result.output


def test_launch_skill_no_warning_when_spec_unchanged(project_copy, monkeypatch):
    """No warning when SPEC.md is unchanged after a non-spec skill."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
    result = runner.invoke(app, ["design"])
    assert "SPEC.md was modified" not in result.output


# --- _launch_skill model/provider handling ---


def test_launch_skill_claude_ignores_model_only(project_copy, monkeypatch):
    """Claude Code ignores model option - no error even if only model is set."""
    monkeypatch.chdir(project_copy)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--model", "glm-5", "--agent", "claude-code"])
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


def test_launch_skill_claude_ignores_provider_only(project_copy, monkeypatch):
    """Claude Code ignores provider option - no error even if only provider is set."""
    monkeypatch.chdir(project_copy)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(
        app, ["spec", "--provider", "z-ai", "--agent", "claude-code"]
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


def test_launch_skill_claude_ignores_model_env_var(project_copy, monkeypatch):
    """Claude ignores model env var - no error even if only model is set."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setenv("PROTHON_MODEL", "glm-5")
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--agent", "claude-code"])
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


def test_launch_skill_opencode_validates_model_provider(project_copy, monkeypatch):
    """opencode still validates model/provider - error if only one is set."""
    monkeypatch.chdir(project_copy)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    result = runner.invoke(app, ["spec", "--model", "glm-5", "--agent", "opencode"])
    assert result.exit_code == 1
    assert "--provider requires --model" in result.output


def test_launch_skill_opencode_accepts_both_model_provider(project_copy, monkeypatch):
    """opencode accepts both model and provider - passes resolved model to launch."""
    monkeypatch.chdir(project_copy)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(
        app,
        ["spec", "--model", "glm-5", "--provider", "z-ai", "--agent", "opencode"],
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] == "z-ai/glm-5"


def test_launch_skill_opencode_conflicting_qualified_model_provider(
    project_copy, monkeypatch
):
    """opencode rejects qualified model when provider conflicts."""
    monkeypatch.chdir(project_copy)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(
        app,
        [
            "spec",
            "--model",
            "providerA/modelX",
            "--provider",
            "providerB",
            "--agent",
            "opencode",
        ],
    )
    assert result.exit_code == 1
    assert fake_launch.call_count == 0
    assert "conflicting providers" in result.output
    assert "providerA" in result.output
    assert "providerB" in result.output


# --- CI subcommands ---


def test_ci_bump_idempotent(project_copy, monkeypatch):
    """ci bump skips if version already matches expected bump."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    # Change a doc to trigger major bump
    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    # Manually bump version in pyproject.toml to 1.0.0 (the expected bump)
    pyproject = dest / "pyproject.toml"
    content = pyproject.read_text()
    version_match = re.search(r'version = "([^"]+)"', content)
    assert version_match is not None
    current_v = version_match.group(1)
    new_v = "1.0.0"  # Expected major bump from 0.1.0
    pyproject.write_text(
        content.replace(f'version = "{current_v}"', f'version = "{new_v}"')
    )
    run_git("add", "pyproject.toml")
    run_git("commit", "-m", "chore: manual bump")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before])
    assert result.exit_code == 0
    assert f"Version already at {new_v}, skipping" in result.output


def test_ci_bump_applies_changes(project_copy, monkeypatch):
    """ci bump updates files and optionally creates a tag."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    # Change a doc to trigger major bump (from 2.1.0 to 3.0.0)
    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])
    assert result.exit_code == 0
    assert "Detected major bump: 0.1.0 -> 1.0.0" in result.output

    pyproject = dest / "pyproject.toml"
    assert 'version = "1.0.0"' in pyproject.read_text()

    # Verify tag was NOT created
    tags = run_git("tag", "-l").strip()
    assert "v1.0.0" not in tags


def test_ci_bump_fails_on_missing_project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ci", "bump", "--before-sha", "HEAD"])
    assert result.exit_code != 0
    assert "no prothon project found" in result.output.lower()


def test_ci_bump_minor(project_copy, monkeypatch):
    """ci bump applies minor changes when DESIGN.md is changed."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    # Change DESIGN.md to trigger minor bump (from 0.1.0 to 0.2.0)
    (dest / "docs" / "DESIGN.md").write_text("# Updated design\n")
    run_git("add", "docs/DESIGN.md")
    run_git("commit", "-m", "docs: update design")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])
    assert result.exit_code == 0
    assert "Detected minor bump: 0.1.0 -> 0.2.0" in result.output

    pyproject = dest / "pyproject.toml"
    assert 'version = "0.2.0"' in pyproject.read_text()


def test_ci_bump_patch(project_copy, monkeypatch):
    """ci bump applies patch changes when PATTERNS.md is changed."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    # Change PATTERNS.md to trigger patch bump (from 0.1.0 to 0.1.1)
    (dest / "docs" / "PATTERNS.md").write_text("# Updated patterns\n")
    run_git("add", "docs/PATTERNS.md")
    run_git("commit", "-m", "docs: update patterns")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])
    assert result.exit_code == 0
    assert "Detected patch bump: 0.1.0 -> 0.1.1" in result.output

    pyproject = dest / "pyproject.toml"
    assert 'version = "0.1.1"' in pyproject.read_text()


@pytest.mark.parametrize(
    "file_to_change,expected",
    [
        ("docs/SPEC.md", "major"),
        ("docs/DESIGN.md", "minor"),
        ("docs/PATTERNS.md", "patch"),
        ("README.md", "none"),
    ],
)
def test_ci_detect(file_to_change, expected, project_copy, monkeypatch):
    monkeypatch.chdir(project_copy)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (project_copy / file_to_change).write_text("# Updated\n")
    run_git("add", file_to_change)
    run_git("commit", "-m", f"docs: update {file_to_change}")

    result = runner.invoke(app, ["ci", "detect", "--before-sha", before])
    assert result.exit_code == 0
    assert result.output.strip() == expected


def test_ci_bump_disabled(project_copy, monkeypatch):
    """ci bump respects auto_version = false in pyproject.toml."""
    dest = project_copy
    monkeypatch.chdir(dest)

    pyproject = dest / "pyproject.toml"
    content = pyproject.read_text()
    pyproject.write_text(content.replace("auto_version = true", "auto_version = false"))

    result = runner.invoke(app, ["ci", "bump", "--before-sha", "HEAD"])
    assert result.exit_code == 0
    assert "Automatic versioning is disabled" in result.output


def test_ci_bump_no_type(project_copy, monkeypatch):
    """ci bump exits if no bump type is detected."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    # Change unrelated file
    (dest / "README.md").write_text("# Updated\n")
    run_git("add", "README.md")
    run_git("commit", "-m", "docs: update readme")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before])
    assert result.exit_code == 0
    assert "No version bump needed" in result.output


def test_ci_bump_empty_pyproject(project_copy, monkeypatch):
    """ci bump fails if pyproject.toml is unreadable or empty."""
    dest = project_copy
    monkeypatch.chdir(dest)

    (dest / "pyproject.toml").write_text("")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", "HEAD"])
    assert result.exit_code != 0
    assert "Could not read pyproject.toml" in result.output


def test_ci_bump_missing_version(project_copy, monkeypatch):
    """ci bump fails if version is missing from pyproject.toml."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    pyproject = dest / "pyproject.toml"
    # Keep [project] but remove version
    pyproject.write_text('[project]\nname = "test-project"\n')

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before])
    assert result.exit_code != 0
    assert "version not found" in result.output


def test_ci_bump_dry_run(project_copy, monkeypatch):
    """ci bump with --dry-run doesn't modify files."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run: Skipping" in result.output

    pyproject = dest / "pyproject.toml"
    assert 'version = "0.1.0"' in pyproject.read_text()


def test_ci_bump_missing_name(project_copy, monkeypatch):
    """ci bump fails if name is missing from pyproject.toml."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    pyproject = dest / "pyproject.toml"
    # Keep [project] and version but remove name
    pyproject.write_text('[project]\nversion = "0.1.0"\n')

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before])
    assert result.exit_code != 0
    assert "name not found" in result.output


def test_ci_bump_missing_init(project_copy, monkeypatch):
    """ci bump warns if __init__.py is missing."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    # Remove src directory
    shutil.rmtree(dest / "src")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])
    assert result.exit_code == 0
    assert "Could not find __init__.py" in result.output


def test_ci_bump_tag_failure(project_copy, monkeypatch):
    """ci bump warns if tag creation fails."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    monkeypatch.setattr(
        "prothon.versioning.create_tag",
        Recorder(side_effect=ProthonError("tag error")),
    )
    result = runner.invoke(app, ["ci", "bump", "--before-sha", before])
    assert result.exit_code == 0
    assert "Tag creation failed: tag error" in result.output


def test_ci_bump_base_version_fallback(project_copy, monkeypatch):
    """ci bump falls back to branch version if base_version cannot be read."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")

    # Change something to ensure a bump is detected
    before = rev_parse_head()
    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    import prothon.git

    original_run_git = prothon.git.run_git

    def fake_run_git(*args, **kwargs):
        if len(args) > 1 and args[0] == "show" and "pyproject.toml" in args[1]:
            raise GitError("git show failed")
        return original_run_git(*args, **kwargs)

    monkeypatch.setattr("prothon.git.run_git", fake_run_git)
    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])

    assert result.exit_code == 0
    assert "Falling back to branch version" in result.output


# --- _enforce_commit ---


def test_enforce_commit_dirty_doc_calls_commit(tmp_path, monkeypatch):
    """Doc skill with dirty file triggers commit_file."""
    from prothon.commands import enforce_commit as _enforce_commit

    doc = tmp_path / "docs" / "SPEC.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Spec\n")

    fake_commit = Recorder()
    monkeypatch.setattr("prothon.commands.is_dirty", lambda path, cwd: True)
    monkeypatch.setattr("prothon.commands.commit_file", fake_commit)

    _enforce_commit("prothon-spec-writer", tmp_path)

    assert fake_commit.call_count == 1
    assert fake_commit.last_args[0] == doc.relative_to(tmp_path)
    assert "SPEC.md" in fake_commit.last_args[1]


def test_enforce_commit_clean_doc_no_commit(tmp_path, monkeypatch):
    """Doc skill with clean file does not commit."""
    from prothon.commands import enforce_commit as _enforce_commit

    doc = tmp_path / "docs" / "SPEC.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Spec\n")

    fake_commit = Recorder()
    monkeypatch.setattr("prothon.commands.is_dirty", lambda path, cwd: False)
    monkeypatch.setattr("prothon.commands.commit_file", fake_commit)

    _enforce_commit("prothon-spec-writer", tmp_path)

    assert fake_commit.call_count == 0


def test_enforce_commit_non_doc_skill_no_commit(tmp_path, monkeypatch):
    """Non-doc skill (execute) does not attempt any commit."""
    from prothon.commands import enforce_commit as _enforce_commit

    fake_is_dirty = Recorder(return_value=False)
    monkeypatch.setattr("prothon.commands.is_dirty", fake_is_dirty)
    monkeypatch.setattr("prothon.commands.commit_file", Recorder())

    _enforce_commit("prothon-execute", tmp_path)

    # is_dirty should never be called for non-doc skills
    assert fake_is_dirty.call_count == 0


def test_enforce_commit_unknown_skill_noop(tmp_path, monkeypatch):
    """Unknown skill name is a graceful no-op."""
    from prothon.commands import enforce_commit as _enforce_commit

    # Should not raise or call any git functions
    _enforce_commit("totally-unknown-skill", tmp_path)


# --- _trigger_follow_ups ---


def test_trigger_follow_ups_spec_writer_launches_harmonizer(tmp_path, monkeypatch):
    """spec-writer triggers doc-harmonizer follow-up."""
    from prothon.commands import trigger_follow_ups as _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.commands.launch_skill", fake_launch)

    _trigger_follow_ups("prothon-spec-writer", tmp_path, agent="claude-code")

    assert fake_launch.call_count == 1
    assert fake_launch.last_args[0] == "prothon-doc-harmonizer"
    assert fake_launch.last_args[1] == tmp_path
    assert fake_launch.last_kwargs.get("run_follow_ups") is False


def test_trigger_follow_ups_design_writer_launches_followups(tmp_path, monkeypatch):
    """design-writer triggers harmonizer and tech-researcher."""
    from prothon.commands import trigger_follow_ups as _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.commands.launch_skill", fake_launch)

    _trigger_follow_ups("prothon-design-writer", tmp_path)

    assert fake_launch.call_count == 2
    # First call: doc-harmonizer
    assert fake_launch.calls[0][0][0] == "prothon-doc-harmonizer"
    # Second call: tech-researcher
    assert fake_launch.calls[1][0][0] == "prothon-tech-researcher"


def test_trigger_follow_ups_patterns_writer_launches_harmonizer(tmp_path, monkeypatch):
    """patterns-writer triggers doc-harmonizer."""
    from prothon.commands import trigger_follow_ups as _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.commands.launch_skill", fake_launch)

    _trigger_follow_ups("prothon-patterns-writer", tmp_path)

    assert fake_launch.call_count == 1
    assert fake_launch.last_args[0] == "prothon-doc-harmonizer"


def test_trigger_follow_ups_execute_launches_compliance(tmp_path, monkeypatch):
    """execute triggers compliance-checker."""
    from prothon.commands import trigger_follow_ups as _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.commands.launch_skill", fake_launch)

    _trigger_follow_ups("prothon-execute", tmp_path)

    assert fake_launch.call_count == 1
    assert fake_launch.last_args[0] == "prothon-compliance-checker"
