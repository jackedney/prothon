"""Tests for workflow CLI commands."""

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from prothon.cli import app, find_project_root, generate, launch_claude


def test_find_project_root_from_project_dir(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("project_name: test")
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_from_subdirectory(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("project_name: test")
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) == tmp_path


def test_find_project_root_not_found(tmp_path):
    assert find_project_root(tmp_path) is None


def test_launch_claude_calls_subprocess(tmp_path):
    with patch("prothon.cli.subprocess.run") as mock_run:
        with patch("prothon.cli.shutil.which", return_value="/usr/bin/claude"):
            launch_claude("spec-writer", tmp_path)
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd = call_args.args[0]
    assert cmd[0] == "claude"
    assert cmd[1] == "--dangerously-skip-permissions"
    assert "spec-writer" in cmd[2].lower() or "spec" in cmd[2].lower()
    assert call_args.kwargs["cwd"] == tmp_path


def test_launch_claude_raises_when_claude_not_found(tmp_path):
    with patch("prothon.cli.shutil.which", return_value=None):
        with pytest.raises((SystemExit, typer.Exit)):
            launch_claude("spec-writer", tmp_path)


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
    assert "Not inside a prothon-generated project" in result.output


def test_design_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["design"])
    assert result.exit_code != 0
    assert "Not inside a prothon-generated project" in result.output


def test_patterns_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["patterns"])
    assert result.exit_code != 0
    assert "Not inside a prothon-generated project" in result.output


def test_compliance_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["compliance"])
    assert result.exit_code != 0
    assert "Not inside a prothon-generated project" in result.output


def test_spec_launches_claude_in_project(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.shutil.which", return_value="/usr/bin/claude"):
        with patch("prothon.cli.subprocess.run") as mock_run:
            runner.invoke(app, ["spec"])
    claude_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "claude"]
    assert len(claude_calls) == 1
    cmd = claude_calls[0].args[0]
    assert cmd[0] == "claude"
    assert cmd[1] == "--dangerously-skip-permissions"
    assert "spec" in cmd[2].lower()


def test_design_launches_single_session(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.shutil.which", return_value="/usr/bin/claude"):
        with patch("prothon.cli.subprocess.run") as mock_run:
            runner.invoke(app, ["design"])
    claude_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "claude"]
    assert len(claude_calls) == 1
    cmd = claude_calls[0].args[0]
    assert cmd[0] == "claude"
    assert cmd[1] == "--dangerously-skip-permissions"
    assert "design" in cmd[2].lower()
