"""Tests for workflow CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from prothon.assistant import ClaudeCodeBackend, launch
from prothon.cli import app
from prothon.exceptions import AssistantNotFoundError
from prothon.project import find_project_root
from prothon.scaffold import generate


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


def test_launch_calls_subprocess(tmp_path):
    with patch("prothon.assistant.subprocess.run") as mock_run:
        with patch("prothon.assistant.shutil.which", return_value="/usr/bin/claude"):
            backend = ClaudeCodeBackend()
            with patch.object(backend, "sync_skills"):
                launch(backend, "prothon-spec-writer", tmp_path)
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd = call_args.args[0]
    assert cmd == ["claude", "--dangerously-skip-permissions", "/prothon-spec-writer"]
    assert call_args.kwargs["cwd"] == tmp_path


def test_launch_raises_when_assistant_not_found(tmp_path):
    with patch("prothon.assistant.shutil.which", return_value=None):
        backend = ClaudeCodeBackend()
        with pytest.raises(AssistantNotFoundError):
            launch(backend, "prothon-spec-writer", tmp_path)


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
    with patch("prothon.cli.launch") as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_backend = mock_get_backend.return_value
            runner.invoke(app, ["spec"])
    mock_launch.assert_called_once_with(mock_backend, "prothon-spec-writer", dest)


def test_design_launches_single_session(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.launch") as mock_launch:
        with patch("prothon.cli.get_backend") as mock_get_backend:
            mock_backend = mock_get_backend.return_value
            runner.invoke(app, ["design"])
    mock_launch.assert_called_once_with(mock_backend, "prothon-design-writer", dest)
