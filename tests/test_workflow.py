"""Tests for workflow CLI commands."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from prothon.cli import find_project_root, launch_claude


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
            launch_claude("You are a spec writer.", tmp_path)
    mock_run.assert_called_once_with(
        ["claude", "--append-system-prompt", "You are a spec writer."],
        cwd=tmp_path,
    )


def test_launch_claude_raises_when_claude_not_found(tmp_path):
    with patch("prothon.cli.shutil.which", return_value=None):
        with pytest.raises((SystemExit, typer.Exit)):
            launch_claude("prompt", tmp_path)
