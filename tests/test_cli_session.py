"""Tests for CLI session commands: spec, design, patterns, execute, compliance, refactor."""

from __future__ import annotations

import pytest
from tests.fakes import FakeAssistantBackend, Recorder
from prothon.cli import app
from prothon.exceptions import AssistantNotFoundError, ProthonError
from typer.testing import CliRunner

runner = CliRunner()


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
    assert "Install:" in result.output
    assert "anthropic.com" in result.output
    assert "XX" not in result.output


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


@pytest.mark.parametrize(
    "extra_args,extra_env",
    [
        (["--model", "glm-5"], {}),
        (["--provider", "z-ai"], {}),
        ([], {"PROTHON_MODEL": "glm-5"}),
    ],
)
def test_launch_skill_claude_ignores_model_options(
    extra_args, extra_env, project_copy, monkeypatch
):
    """Claude Code ignores model/provider options and env vars."""
    monkeypatch.chdir(project_copy)
    for k, v in extra_env.items():
        monkeypatch.setenv(k, v)
    fake_launch = Recorder(return_value=0)
    monkeypatch.setattr(
        "prothon.commands.get_backend",
        Recorder(return_value=FakeAssistantBackend(name="Claude Code")),
    )
    monkeypatch.setattr("prothon.commands.launch", fake_launch)
    result = runner.invoke(app, ["spec", "--agent", "claude-code", *extra_args])
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


@pytest.mark.parametrize(
    "skill,expected",
    [
        ("prothon-spec-writer", ["prothon-doc-harmonizer"]),
        (
            "prothon-design-writer",
            ["prothon-doc-harmonizer", "prothon-tech-researcher"],
        ),
        ("prothon-patterns-writer", ["prothon-doc-harmonizer"]),
        ("prothon-execute", ["prothon-compliance-checker"]),
    ],
)
def test_trigger_follow_ups(skill, expected, tmp_path, monkeypatch):
    """Each doc skill triggers the correct follow-up sequence."""
    from prothon.commands import trigger_follow_ups as _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.commands.launch_skill", fake_launch)

    _trigger_follow_ups(skill, tmp_path)

    assert fake_launch.call_count == len(expected)
    for i, name in enumerate(expected):
        assert fake_launch.calls[i][0][0] == name


def test_trigger_follow_ups_spec_disables_follow_ups(tmp_path, monkeypatch):
    """spec-writer passes run_follow_ups=False to prevent recursion."""
    from prothon.commands import trigger_follow_ups as _trigger_follow_ups

    fake_launch = Recorder()
    monkeypatch.setattr("prothon.commands.launch_skill", fake_launch)

    _trigger_follow_ups("prothon-spec-writer", tmp_path, agent="claude-code")

    assert fake_launch.last_kwargs.get("run_follow_ups") is False
