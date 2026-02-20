"""Tests for workflow CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from prothon.cli import app
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
