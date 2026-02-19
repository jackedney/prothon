"""Tests for Copier-based project scaffolding."""

from __future__ import annotations

import os

import pytest

from prothon.scaffold import _template_dir, generate


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
