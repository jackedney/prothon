"""Tests for Copier-based project scaffolding."""

from __future__ import annotations

import os

import pytest

from prothon.exceptions import GitError, ProjectAlreadyInitError
from prothon.git import run_git
from prothon.scaffold import _template_dir, generate, init_existing
from tests.conftest import assert_symlink_to


@pytest.fixture
def scaffold_data():
    """Return a complete data dict for non-interactive generation."""
    return {
        "module_name": "test_project",
        "description": "A test project",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "python_version": "3.13",
        "license": "MIT",
    }


@pytest.fixture
def generated_project(tmp_path, scaffold_data):
    """Generate a project into a temp directory and return its path."""
    dest = tmp_path / "test-project"
    generate(dest, data=scaffold_data)
    return dest


def test_template_dir_exists():
    """_template_dir() returns a valid directory."""
    result = _template_dir()
    assert result.is_dir(), f"Template dir does not exist: {result}"


def test_template_dir_contains_copier_yml():
    """_template_dir() contains a copier.yml file."""
    result = _template_dir()
    assert (result / "copier.yml").exists()


def test_creates_destination_directory(generated_project):
    """Destination directory is created."""
    assert generated_project.is_dir()


def test_renders_pyproject_toml(generated_project):
    """pyproject.toml is rendered without Jinja placeholders."""
    pyproject = generated_project / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text()
    assert "{{ " not in content
    assert 'name = "test-project"' in content


def test_module_init_exists(generated_project):
    """src/{module_name}/__init__.py exists."""
    init = generated_project / "src" / "test_project" / "__init__.py"
    assert init.exists()


def test_module_init_has_docstring(generated_project):
    """__init__.py contains the rendered description."""
    init = generated_project / "src" / "test_project" / "__init__.py"
    content = init.read_text()
    assert '"A test project"' in content


def test_creates_symlinks(generated_project):
    """CLAUDE.md, GEMINI.md, AGENT.md are symlinks to AGENTS.md."""
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = generated_project / name
        assert link.is_symlink(), f"{name} is not a symlink"
        assert os.readlink(str(link)) == "AGENTS.md"


def test_creates_agents_skills_dir(generated_project):
    """.agents/skills directory is created."""
    skills_dir = generated_project / ".agents" / "skills"
    assert skills_dir.is_dir()


def test_git_initialized(generated_project):
    """Git repository is initialized with an initial commit."""
    assert (generated_project / ".git").is_dir()


def test_copier_answers_written(generated_project):
    """.copier-answers.yml is written by Copier."""
    answers = generated_project / ".copier-answers.yml"
    assert answers.exists()
    content = answers.read_text()
    assert "module_name" in content


def test_creates_doc_scaffolds(generated_project):
    """docs/SPEC.md, DESIGN.md, PATTERNS.md are created."""
    for name in ("SPEC.md", "DESIGN.md", "PATTERNS.md"):
        doc = generated_project / "docs" / name
        assert doc.exists()
        assert doc.stat().st_size > 0


def test_copies_plain_files(generated_project):
    """.gitignore is copied as-is."""
    assert (generated_project / ".gitignore").exists()


def test_creates_agents_md(generated_project):
    """AGENTS.md is rendered with the project name."""
    agents = generated_project / "AGENTS.md"
    assert agents.exists()
    content = agents.read_text()
    assert "# test-project" in content


# --- init_existing ---


def test_init_existing_raises_when_not_git_repo(tmp_path):
    """init_existing raises GitError when cwd is not a git repository."""
    with pytest.raises(GitError, match="not a git repository"):
        init_existing(cwd=tmp_path)


def test_init_existing_raises_when_spec_exists(tmp_path):
    """init_existing raises ProjectAlreadyInitError when docs/SPEC.md exists."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# existing")
    with pytest.raises(ProjectAlreadyInitError):
        init_existing(cwd=tmp_path)


def test_init_existing_creates_all_artifacts(tmp_path):
    """init_existing creates docs, AGENTS.md, symlinks, and skills dir."""
    run_git("init", cwd=tmp_path)
    init_existing(cwd=tmp_path)

    assert (tmp_path / "docs" / "SPEC.md").exists()
    assert (tmp_path / "docs" / "SPEC.md").stat().st_size > 0
    assert (tmp_path / "docs" / "DESIGN.md").exists()
    assert (tmp_path / "docs" / "DESIGN.md").stat().st_size > 0
    assert (tmp_path / "docs" / "PATTERNS.md").exists()
    assert (tmp_path / "docs" / "PATTERNS.md").stat().st_size > 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "AGENTS.md").stat().st_size > 0
    assert (tmp_path / ".agents" / "skills").is_dir()
    assert_symlink_to(tmp_path / "CLAUDE.md", "AGENTS.md")
    assert_symlink_to(tmp_path / "GEMINI.md", "AGENTS.md")
    assert_symlink_to(tmp_path / "AGENT.md", "AGENTS.md")


def test_init_existing_returns_created_paths(tmp_path):
    """init_existing returns a list containing all created paths."""
    run_git("init", cwd=tmp_path)
    created = init_existing(cwd=tmp_path)

    expected_names = {
        "SPEC.md",
        "DESIGN.md",
        "PATTERNS.md",
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "AGENT.md",
        "skills",
    }
    created_names = {p.name for p in created}
    assert expected_names == created_names


def test_init_existing_does_not_modify_existing_files(tmp_path):
    """init_existing leaves pre-existing files untouched."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    init_existing(cwd=tmp_path)
    assert "[tool.ruff]" in (tmp_path / "pyproject.toml").read_text()


def test_init_existing_spec_scaffold_has_required_sections(tmp_path):
    """Scaffolded SPEC.md contains all required section headings."""
    run_git("init", cwd=tmp_path)
    init_existing(cwd=tmp_path)
    content = (tmp_path / "docs" / "SPEC.md").read_text()
    assert "## Purpose" in content
    assert "## Requirements" in content
    assert "## Constraints" in content
    assert "## Out of Scope" in content
