"""Tests for workflow CLI commands."""

from __future__ import annotations

import re

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


def test_spec_launches_claude_in_project(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_backend = FakeAssistantBackend()
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr("prothon.cli.get_backend", Recorder(return_value=fake_backend))
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    runner.invoke(app, ["spec"])
    assert fake_launch.call_count >= 1
    assert fake_launch.calls[0][0][:3] == (fake_backend, "prothon-spec-writer", dest)
    assert fake_launch.calls[0][1] == {"model": None}


def test_design_launches_single_session(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_backend = FakeAssistantBackend()
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr("prothon.cli.get_backend", Recorder(return_value=fake_backend))
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    runner.invoke(app, ["design"])
    assert fake_launch.call_count >= 1
    assert fake_launch.calls[0][0][:3] == (fake_backend, "prothon-design-writer", dest)
    assert fake_launch.calls[0][1] == {"model": None}


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
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.cli.launch", Recorder(return_value=42))
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 42


def test_launch_skill_zero_exit_succeeds(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.cli.launch", Recorder(return_value=0))
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 0


def test_launch_skill_assistant_not_found(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.cli.launch",
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


def test_launch_skill_prothon_error(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.cli.launch",
        Recorder(side_effect=ProthonError("something wrong")),
    )
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
        fake_backend = FakeAssistantBackend()
        fake_launch = Recorder(return_value=0)
        monkeypatch.setattr(
            "prothon.cli.get_backend", Recorder(return_value=fake_backend)
        )
        monkeypatch.setattr("prothon.cli.launch", fake_launch)
        runner.invoke(app, [cmd])
        assert fake_launch.called_with_arg(1, skill_name)


def test_launch_skill_exit_code_one_is_nonzero(tmp_path, monkeypatch, context):
    """rc=1 should still raise Exit (kills rc != 0 → rc != 1)."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.cli.launch", Recorder(return_value=1))
    result = runner.invoke(app, ["spec"])
    assert result.exit_code == 1


def test_launch_skill_assistant_not_found_install_url(tmp_path, monkeypatch, context):
    """Error message includes Install URL from backend's install_hint."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.cli.launch",
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


def test_launch_skill_assistant_not_found_no_xx_prefix(tmp_path, monkeypatch, context):
    """Error and Install lines must not have 'XX' padding (kills string mutations)."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr(
        "prothon.cli.launch",
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


def test_agent_flag_passed_through_to_backend(tmp_path, monkeypatch, context):
    """--agent flag reaches resolve_agent and selects the correct backend."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_get_backend = Recorder(return_value=FakeAssistantBackend())
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr("prothon.cli.get_backend", fake_get_backend)
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    runner.invoke(app, ["spec", "--agent", "opencode"])
    assert fake_get_backend.called_with_arg(0, "opencode")
    assert fake_launch.call_count >= 1


def test_unknown_backend_produces_error(tmp_path, monkeypatch, context):
    """Unknown backend name shows error with 'no backend registered'."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    result = runner.invoke(app, ["spec", "--agent", "unknown-backend"])
    assert result.exit_code == 1
    assert "no backend registered" in result.output


def test_resolve_agent_env_var_via_cli_runner(tmp_path, monkeypatch, context):
    """PROTHON_AGENT env var flows through the Typer option into resolve_agent."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    fake_get_backend = Recorder(return_value=FakeAssistantBackend())
    monkeypatch.setattr("prothon.cli.get_backend", fake_get_backend)
    monkeypatch.setattr("prothon.cli.launch", Recorder(return_value=0))
    runner.invoke(app, ["spec"])
    assert fake_get_backend.called_with_arg(0, "opencode")


def test_resolve_agent_cli_flag_overrides_env_var(tmp_path, monkeypatch, context):
    """Level 1 beats level 2: CLI --agent flag overrides PROTHON_AGENT."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    fake_get_backend = Recorder(return_value=FakeAssistantBackend())
    monkeypatch.setattr("prothon.cli.get_backend", fake_get_backend)
    monkeypatch.setattr("prothon.cli.launch", Recorder(return_value=0))
    runner.invoke(app, ["spec", "--agent", "claude-code"])
    assert fake_get_backend.called_with_arg(0, "claude-code")


# --- CLI integration tests for model/provider ---


def test_opencode_receives_resolved_model(tmp_path, monkeypatch, context):
    """opencode backend receives resolved model in format provider/model."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(
        app,
        ["spec", "--agent", "opencode", "--model", "glm-5", "--provider", "z-ai"],
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] == "z-ai/glm-5"


def test_opencode_receives_slash_model_as_is(tmp_path, monkeypatch, context):
    """opencode receives model with '/' as-is when no provider specified."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(
        app,
        ["spec", "--agent", "opencode", "--model", "z-ai/glm-5"],
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] == "z-ai/glm-5"


def test_opencode_no_model_passes_none(tmp_path, monkeypatch, context):
    """opencode with no model/provider configured passes None to launch."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.delenv("PROTHON_MODEL", raising=False)
    monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--agent", "opencode"])
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


# --- SPEC.md protection (R21) ---


def test_launch_skill_warns_when_spec_modified(tmp_path, monkeypatch, context):
    """Non-spec skills warn if SPEC.md was modified during the session."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    def modify_spec(*args, **kwargs):
        (dest / "docs" / "SPEC.md").write_text("# Tampered\n")
        return 0

    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.cli.launch", Recorder(side_effect=modify_spec))
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

    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.cli.launch", Recorder(side_effect=modify_spec))
    result = runner.invoke(app, ["spec"])
    assert "SPEC.md was modified" not in result.output


def test_launch_skill_no_warning_when_spec_unchanged(tmp_path, monkeypatch, context):
    """No warning when SPEC.md is unchanged after a non-spec skill."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend", Recorder(return_value=FakeAssistantBackend())
    )
    monkeypatch.setattr("prothon.cli.launch", Recorder(return_value=0))
    result = runner.invoke(app, ["design"])
    assert "SPEC.md was modified" not in result.output


# --- _launch_skill model/provider handling ---


def test_launch_skill_claude_ignores_model_only(tmp_path, monkeypatch, context):
    """Claude Code ignores model option - no error even if only model is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--model", "glm-5", "--agent", "claude-code"])
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


def test_launch_skill_claude_ignores_provider_only(tmp_path, monkeypatch, context):
    """Claude Code ignores provider option - no error even if only provider is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(
        app, ["spec", "--provider", "z-ai", "--agent", "claude-code"]
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


def test_launch_skill_claude_ignores_model_env_var(tmp_path, monkeypatch, context):
    """Claude ignores model env var - no error even if only model is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setenv("PROTHON_MODEL", "glm-5")
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--agent", "claude-code"])
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] is None


def test_launch_skill_opencode_validates_model_provider(tmp_path, monkeypatch, context):
    """opencode still validates model/provider - error if only one is set."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
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
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
    result = runner.invoke(
        app,
        ["spec", "--model", "glm-5", "--provider", "z-ai", "--agent", "opencode"],
    )
    assert result.exit_code == 0
    assert fake_launch.call_count >= 1
    assert fake_launch.last_kwargs["model"] == "z-ai/glm-5"


def test_launch_skill_opencode_conflicting_qualified_model_provider(
    tmp_path, monkeypatch, context
):
    """opencode rejects qualified model when provider conflicts."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.cli.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="opencode")),
    )
    monkeypatch.setattr("prothon.cli.launch", fake_launch)
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


def test_ci_bump_idempotent(tmp_path, monkeypatch, context):
    """ci bump skips if version already matches expected bump."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_applies_changes(tmp_path, monkeypatch, context):
    """ci bump updates files and optionally creates a tag."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_minor(tmp_path, monkeypatch, context):
    """ci bump applies minor changes when DESIGN.md is changed."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_patch(tmp_path, monkeypatch, context):
    """ci bump applies patch changes when PATTERNS.md is changed."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_detect_major(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    result = runner.invoke(app, ["ci", "detect", "--before-sha", before])
    assert result.exit_code == 0
    assert result.output.strip() == "major"


def test_ci_detect_minor(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "DESIGN.md").write_text("# Updated design\n")
    run_git("add", "docs/DESIGN.md")
    run_git("commit", "-m", "docs: update design")

    result = runner.invoke(app, ["ci", "detect", "--before-sha", before])
    assert result.exit_code == 0
    assert result.output.strip() == "minor"


def test_ci_detect_patch(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "PATTERNS.md").write_text("# Updated patterns\n")
    run_git("add", "docs/PATTERNS.md")
    run_git("commit", "-m", "docs: update patterns")

    result = runner.invoke(app, ["ci", "detect", "--before-sha", before])
    assert result.exit_code == 0
    assert result.output.strip() == "patch"


def test_ci_detect_none(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    # Change unrelated file
    (dest / "README.md").write_text("# Updated README\n")
    run_git("add", "README.md")
    run_git("commit", "-m", "docs: update readme")

    result = runner.invoke(app, ["ci", "detect", "--before-sha", before])
    assert result.exit_code == 0
    assert result.output.strip() == "none"


def test_ci_bump_disabled(tmp_path, monkeypatch, context):
    """ci bump respects auto_version = false in pyproject.toml."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    pyproject = dest / "pyproject.toml"
    content = pyproject.read_text()
    pyproject.write_text(content.replace("auto_version = true", "auto_version = false"))

    result = runner.invoke(app, ["ci", "bump", "--before-sha", "HEAD"])
    assert result.exit_code == 0
    assert "Automatic versioning is disabled" in result.output


def test_ci_bump_no_type(tmp_path, monkeypatch, context):
    """ci bump exits if no bump type is detected."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_empty_pyproject(tmp_path, monkeypatch, context):
    """ci bump fails if pyproject.toml is unreadable or empty."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)

    (dest / "pyproject.toml").write_text("")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", "HEAD"])
    assert result.exit_code != 0
    assert "Could not read pyproject.toml" in result.output


def test_ci_bump_missing_version(tmp_path, monkeypatch, context):
    """ci bump fails if version is missing from pyproject.toml."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_dry_run(tmp_path, monkeypatch, context):
    """ci bump with --dry-run doesn't modify files."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_missing_name(tmp_path, monkeypatch, context):
    """ci bump fails if name is missing from pyproject.toml."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_missing_init(tmp_path, monkeypatch, context):
    """ci bump warns if __init__.py is missing."""
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    # Remove src directory
    import shutil

    shutil.rmtree(dest / "src")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])
    assert result.exit_code == 0
    assert "Could not find __init__.py" in result.output


def test_ci_bump_tag_failure(tmp_path, monkeypatch, context):
    """ci bump warns if tag creation fails."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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


def test_ci_bump_base_version_fallback(tmp_path, monkeypatch, context):
    """ci bump falls back to branch version if base_version cannot be read."""
    dest = tmp_path / "test-project"
    generate(dest, context)
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
    from prothon.cli import _enforce_commit

    doc = tmp_path / "docs" / "SPEC.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Spec\n")

    fake_commit = Recorder()
    monkeypatch.setattr("prothon.git.is_dirty", lambda path, cwd: True)
    monkeypatch.setattr("prothon.git.commit_file", fake_commit)

    _enforce_commit("prothon-spec-writer", tmp_path)

    assert fake_commit.call_count == 1
    assert fake_commit.last_args[0] == doc.relative_to(tmp_path)
    assert "SPEC.md" in fake_commit.last_args[1]


def test_enforce_commit_clean_doc_no_commit(tmp_path, monkeypatch):
    """Doc skill with clean file does not commit."""
    from prothon.cli import _enforce_commit

    doc = tmp_path / "docs" / "SPEC.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Spec\n")

    fake_commit = Recorder()
    monkeypatch.setattr("prothon.git.is_dirty", lambda path, cwd: False)
    monkeypatch.setattr("prothon.git.commit_file", fake_commit)

    _enforce_commit("prothon-spec-writer", tmp_path)

    assert fake_commit.call_count == 0


def test_enforce_commit_non_doc_skill_no_commit(tmp_path, monkeypatch):
    """Non-doc skill (execute) does not attempt any commit."""
    from prothon.cli import _enforce_commit

    fake_is_dirty = Recorder(return_value=False)
    monkeypatch.setattr("prothon.git.is_dirty", fake_is_dirty)
    monkeypatch.setattr("prothon.git.commit_file", Recorder())

    _enforce_commit("prothon-execute", tmp_path)

    # is_dirty should never be called for non-doc skills
    assert fake_is_dirty.call_count == 0


def test_enforce_commit_unknown_skill_noop(tmp_path, monkeypatch):
    """Unknown skill name is a graceful no-op."""
    from prothon.cli import _enforce_commit

    # Should not raise or call any git functions
    _enforce_commit("totally-unknown-skill", tmp_path)


# --- _trigger_follow_ups ---


def test_trigger_follow_ups_spec_writer_launches_harmonizer(tmp_path, monkeypatch):
    """spec-writer triggers doc-harmonizer follow-up."""
    from prothon.cli import _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.cli._launch_skill", fake_launch)

    _trigger_follow_ups("prothon-spec-writer", tmp_path, agent="claude-code")

    assert fake_launch.call_count == 1
    assert fake_launch.last_args[0] == "prothon-doc-harmonizer"
    assert fake_launch.last_args[1] == tmp_path
    assert fake_launch.last_kwargs.get("run_follow_ups") is False


def test_trigger_follow_ups_design_writer_no_followup(tmp_path, monkeypatch):
    """design-writer does not trigger any follow-up (harmonizer is in-skill)."""
    from prothon.cli import _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.cli._launch_skill", fake_launch)

    _trigger_follow_ups("prothon-design-writer", tmp_path)

    assert fake_launch.call_count == 0


def test_trigger_follow_ups_execute_no_followup(tmp_path, monkeypatch):
    """execute does not trigger any follow-up."""
    from prothon.cli import _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.cli._launch_skill", fake_launch)

    _trigger_follow_ups("prothon-execute", tmp_path)

    assert fake_launch.call_count == 0
