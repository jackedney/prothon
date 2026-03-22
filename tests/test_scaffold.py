"""Tests for project scaffolding and adoption."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from prothon.exceptions import GitError, ProjectAlreadyInitError, ProthonError
from prothon.git import run_git
from prothon.scaffold import (
    _DESIGN_SCAFFOLD,
    _GITLAB_VERSION_BUMP,
    _PATTERNS_SCAFFOLD,
    _SPEC_SCAFFOLD,
    _VERSION_BUMP_WORKFLOW,
    _VERSION_TAG_WORKFLOW,
    _template_dir,
    generate,
    init_existing,
)


@pytest.fixture
def context() -> dict[str, str]:
    """Shared project context for scaffolding tests."""
    return {
        "project_name": "test-project",
        "module_name": "test_project",
        "description": "A test project",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "python_version": "3.12",
        "license": "MIT",
    }


def test_template_dir_exists() -> None:
    """The bundled copier template must exist at the project root."""
    path = _template_dir()
    assert path.exists()
    assert (path / "copier.yml").exists()


def test_generate_creates_project(tmp_path: Path, context: dict[str, str]) -> None:
    """generate() must create the project directory and invoke copier."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    assert dest.exists()
    assert (dest / "pyproject.toml").exists()
    assert (dest / "src" / "test_project" / "__init__.py").exists()
    assert (dest / ".git").exists()


def test_generate_initial_commit(tmp_path: Path, context: dict[str, str]) -> None:
    """The generated project must have an initial git commit."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    # Check for commits
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=dest,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Initial commit from prothon template" in result.stdout


def test_generate_creates_agent_symlinks(
    tmp_path: Path, context: dict[str, str]
) -> None:
    """The generated project must include AGENTS.md and symlinks."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    assert (dest / "AGENTS.md").is_file()
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = dest / name
        assert link.is_symlink()
        assert os.readlink(link) == "AGENTS.md"


def test_generate_creates_doc_scaffolds(
    tmp_path: Path, context: dict[str, str]
) -> None:
    """The generated project must include empty SPEC, DESIGN, and PATTERNS."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    docs = dest / "docs"
    assert (docs / "SPEC.md").exists()
    assert (docs / "DESIGN.md").exists()
    assert (docs / "PATTERNS.md").exists()


def test_generate_creates_skills_dir(tmp_path: Path, context: dict[str, str]) -> None:
    """The generated project must include the .agents/skills/ directory."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    assert (dest / ".agents" / "skills").is_dir()


def test_generate_creates_github_workflows(
    tmp_path: Path, context: dict[str, str]
) -> None:
    """The generated project must include GitHub Actions workflows."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    gh = dest / ".github" / "workflows"
    assert (gh / "ci.yml").exists()
    assert (gh / "version-bump.yml").exists()
    assert (gh / "version-tag.yml").exists()


def test_generate_creates_gitlab_ci(tmp_path: Path, context: dict[str, str]) -> None:
    """The generated project must include GitLab CI configuration."""
    dest = tmp_path / "test-project"
    generate(dest, context)

    assert (dest / ".gitlab-ci.yml").exists()


# --- init_existing ---


def test_init_existing_fails_outside_git(tmp_path: Path) -> None:
    """init_existing fails if the target directory is not a git repository."""
    # tmp_path is just a plain directory, no git init
    with pytest.raises(GitError, match="not a git repository"):
        init_existing(cwd=tmp_path)


def test_init_existing_fails_if_already_init(tmp_path: Path) -> None:
    """init_existing fails if docs/SPEC.md already exists."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec")

    with pytest.raises(ProjectAlreadyInitError, match="SPEC.md already exists"):
        init_existing(cwd=tmp_path)


def test_init_existing_creates_common_overlay(tmp_path: Path) -> None:
    """init_existing creates docs, AGENTS.md, symlinks, and skills dir."""
    run_git("init", cwd=tmp_path)
    # Create pyproject.toml so Path B (no copier) is taken
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    created = init_existing(cwd=tmp_path)

    # Verify return list
    assert (tmp_path / "docs" / "SPEC.md") in created
    assert (tmp_path / "AGENTS.md") in created
    assert (tmp_path / "CLAUDE.md") in created
    assert (tmp_path / ".agents" / "skills") in created

    # Verify actual files
    assert (tmp_path / "docs" / "SPEC.md").read_text() == _SPEC_SCAFFOLD
    assert (tmp_path / "docs" / "DESIGN.md").read_text() == _DESIGN_SCAFFOLD
    assert (tmp_path / "docs" / "PATTERNS.md").read_text() == _PATTERNS_SCAFFOLD
    assert (tmp_path / "AGENTS.md").exists()
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        assert (tmp_path / name).is_symlink()
    assert (tmp_path / ".agents" / "skills").is_dir()


def test_init_existing_adds_ci_workflows(tmp_path: Path) -> None:
    """init_existing adds GitHub and GitLab versioning workflows."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    init_existing(cwd=tmp_path)

    assert (
        tmp_path / ".github" / "workflows" / "version-bump.yml"
    ).read_text() == _VERSION_BUMP_WORKFLOW
    assert (
        tmp_path / ".github" / "workflows" / "version-tag.yml"
    ).read_text() == _VERSION_TAG_WORKFLOW
    assert (tmp_path / ".gitlab-ci.yml").read_text() == _GITLAB_VERSION_BUMP


def test_init_existing_preserves_existing_workflows(tmp_path: Path) -> None:
    """init_existing does not overwrite existing CI workflows."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    # Create dummy workflows
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-bump.yml").write_text("custom bump")
    (tmp_path / ".gitlab-ci.yml").write_text("custom gitlab")

    init_existing(cwd=tmp_path)

    assert (gh / "version-bump.yml").read_text() == "custom bump"
    assert (tmp_path / ".gitlab-ci.yml").read_text() == "custom gitlab"


def test_init_existing_appends_to_pyproject(tmp_path: Path) -> None:
    """init_existing adds [tool.prothon.ci] to existing pyproject.toml."""
    run_git("init", cwd=tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    init_existing(cwd=tmp_path)

    content = pyproject.read_text()
    assert "[tool.prothon.ci]" in content
    assert "auto_version = true" in content


def test_init_existing_preserves_prothon_ci_section(tmp_path: Path) -> None:
    """init_existing does not overwrite [tool.prothon.ci] if it exists."""
    run_git("init", cwd=tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""\
[project]
name = "test"

[tool.prothon.ci]
auto_version = false
""")

    init_existing(cwd=tmp_path)

    assert "auto_version = false" in pyproject.read_text()


def test_init_existing_handles_missing_tool_table(tmp_path: Path) -> None:
    """init_existing creates [tool] table if it does not exist."""
    run_git("init", cwd=tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    init_existing(cwd=tmp_path)
    assert "[tool.prothon.ci]" in pyproject.read_text()


def test_init_existing_handles_missing_prothon_table(tmp_path: Path) -> None:
    """init_existing creates [tool.prothon] table if it does not exist."""
    run_git("init", cwd=tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff]\nline-length = 88\n")

    init_existing(cwd=tmp_path)
    assert "[tool.prothon.ci]" in pyproject.read_text()


def test_init_existing_fails_when_pyproject_missing_and_no_data(tmp_path: Path) -> None:
    """init_existing raises ProthonError if Path A triggered without data."""
    run_git("init", cwd=tmp_path)
    # no pyproject.toml, and no data provided
    with pytest.raises(ProthonError, match="project details required"):
        init_existing(cwd=tmp_path, data=None)


def test_init_existing_path_a_calls_copier(tmp_path: Path) -> None:
    """Path A: when pyproject.toml absent, copier.run_copy is called."""
    from unittest.mock import MagicMock, patch

    run_git("init", cwd=tmp_path)

    mock_run_copy = MagicMock()
    data = {
        "module_name": "testmod",
        "description": "test desc",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "python_version": "3.12",
        "license": "MIT",
    }
    with patch("copier.run_copy", mock_run_copy):
        init_existing(cwd=tmp_path, data=data)

    mock_run_copy.assert_called_once()
    args = mock_run_copy.call_args.args
    assert args[0] == str(_template_dir())
    assert args[1] == str(tmp_path)
    kw = mock_run_copy.call_args.kwargs
    assert kw["data"]["module_name"] == "testmod"
    assert kw["defaults"] is True
    assert kw["unsafe"] is True
    assert kw["skip_tasks"] is True
    assert kw["skip_if_exists"] == ["**"]
    assert kw["exclude"] == ["docs/*", "AGENTS.md*"]
    assert kw["vcs_ref"] == "HEAD"


def test_init_existing_path_a_creates_common_overlay(tmp_path: Path) -> None:
    """Path A: common overlay (docs, AGENTS.md, symlinks, skills) still created."""
    from unittest.mock import patch

    run_git("init", cwd=tmp_path)
    data = {
        "module_name": "testmod",
        "description": "test",
        "author_name": "Test",
        "author_email": "test@example.com",
        "python_version": "3.12",
        "license": "MIT",
    }

    with patch("copier.run_copy"):
        init_existing(cwd=tmp_path, data=data)

    assert (tmp_path / "docs" / "SPEC.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").is_symlink()
    assert (tmp_path / ".agents" / "skills").is_dir()


def test_init_existing_path_b_no_copier(tmp_path: Path) -> None:
    """Path B: when pyproject.toml present, copier.run_copy is not called."""
    from unittest.mock import MagicMock, patch

    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    mock_run_copy = MagicMock()
    with patch("copier.run_copy", mock_run_copy):
        init_existing(cwd=tmp_path)

    mock_run_copy.assert_not_called()


def test_init_existing_creates_workflow_without_pyproject(tmp_path: Path) -> None:
    """init_existing creates workflow even when pyproject.toml absent (Path A)."""
    from unittest.mock import patch

    run_git("init", cwd=tmp_path)
    data = {
        "module_name": "testmod",
        "description": "test",
        "author_name": "Test",
        "author_email": "test@example.com",
        "python_version": "3.12",
        "license": "MIT",
    }

    with patch("copier.run_copy"):
        init_existing(cwd=tmp_path, data=data)

    assert (tmp_path / ".github" / "workflows" / "version-bump.yml").exists()
    assert (tmp_path / ".gitlab-ci.yml").exists()
