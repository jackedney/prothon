"""Tests for core CLI commands: new, init, CI bump/detect, validation."""

from __future__ import annotations

import re
import shutil

import pytest
from tests.fakes import Recorder
from prothon.cli import app
from prothon.exceptions import GitError, ProthonError
from prothon.git import rev_parse_head, run_git
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def context():
    return dict(
        project_name="test-project",
        module_name="test_project",
        description="A test project",
        author_name="Test Author",
        author_email="test@example.com",
        python_version="3.13",
        license="MIT",
    )


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


# --- CI subcommands ---


def test_ci_bump_idempotent(project_copy, monkeypatch):
    """ci bump skips if version already matches expected bump."""
    dest = project_copy
    monkeypatch.chdir(dest)
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")
    before = rev_parse_head()

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    pyproject = dest / "pyproject.toml"
    content = pyproject.read_text()
    version_match = re.search(r'version = "([^"]+)"', content)
    assert version_match is not None
    current_v = version_match.group(1)
    new_v = "1.0.0"
    pyproject.write_text(
        content.replace(f'version = "{current_v}"', f'version = "{new_v}"')
    )

    init_file = dest / "src" / "test_project" / "__init__.py"
    if init_file.exists():
        init_content = init_file.read_text()
        init_content = re.sub(
            r'__version__\s*=\s*["\'][^"\']+["\']',
            f'__version__ = "{new_v}"',
            init_content,
        )
        init_file.write_text(init_content)

    run_git("add", "pyproject.toml", "src/test_project/__init__.py")
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

    (dest / "docs" / "SPEC.md").write_text("# Updated spec\n")
    run_git("add", "docs/SPEC.md")
    run_git("commit", "-m", "docs: update spec")

    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])
    assert result.exit_code == 0
    assert "Detected major bump: 0.1.0 -> 1.0.0" in result.output

    pyproject = dest / "pyproject.toml"
    assert 'version = "1.0.0"' in pyproject.read_text()

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
    monkeypatch.setattr("prothon.versioning.run_git", fake_run_git)
    result = runner.invoke(app, ["ci", "bump", "--before-sha", before, "--no-tag"])

    assert result.exit_code == 0
    assert "Falling back to branch version" in result.output
