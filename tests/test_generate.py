"""Tests for project generation."""

import os

import pytest

from prothon.scaffold import generate


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


@pytest.fixture
def generated_project(tmp_path, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    return dest


def test_creates_destination_directory(generated_project):
    assert generated_project.is_dir()


def test_renders_jinja_templates(generated_project):
    pyproject = generated_project / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text()
    assert 'name = "test-project"' in content
    assert "{{ project_name }}" not in content


def test_strips_jinja_suffix(generated_project):
    assert (generated_project / "pyproject.toml").exists()
    assert not (generated_project / "pyproject.toml.jinja").exists()


def test_copies_plain_files(generated_project):
    assert (generated_project / ".gitignore").exists()


def test_templates_directory_paths(generated_project):
    init = generated_project / "src" / "test_project" / "__init__.py"
    assert init.exists()
    assert '"A test project"' in init.read_text()


def test_creates_symlinks(generated_project):
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = generated_project / name
        assert link.is_symlink()
        assert os.readlink(str(link)) == "AGENTS.md"


def test_writes_copier_answers(generated_project):
    answers = generated_project / ".copier-answers.yml"
    assert answers.exists()
    content = answers.read_text()
    assert "module_name: test_project" in content


def test_creates_doc_scaffolds(generated_project):
    for name in ("SPEC.md", "DESIGN.md", "PATTERNS.md"):
        doc = generated_project / "docs" / name
        assert doc.exists()
        assert doc.stat().st_size > 0


def test_creates_agents_skills_dir(generated_project):
    skills_dir = generated_project / ".agents" / "skills"
    assert skills_dir.is_dir()


def test_creates_agents_md(generated_project):
    agents = generated_project / "AGENTS.md"
    assert agents.exists()
    content = agents.read_text()
    assert "# test-project" in content


def test_skips_copier_answers_template(generated_project):
    # The copier-specific answers template should not be rendered
    for p in generated_project.rglob("*"):
        assert "_copier_conf" not in p.name


def test_git_initialized(generated_project):
    assert (generated_project / ".git").is_dir()


def test_authors_omitted_when_both_empty(tmp_path):
    context = {
        "project_name": "no-author",
        "module_name": "no_author",
        "description": "No author project",
        "author_name": "",
        "author_email": "",
        "python_version": "3.13",
        "license": "MIT",
    }
    dest = tmp_path / "no-author"
    generate(dest, context)
    content = (dest / "pyproject.toml").read_text()
    assert "authors" not in content


def test_authors_name_only(tmp_path):
    context = {
        "project_name": "name-only",
        "module_name": "name_only",
        "description": "Name only project",
        "author_name": "Test Author",
        "author_email": "",
        "python_version": "3.13",
        "license": "MIT",
    }
    dest = tmp_path / "name-only"
    generate(dest, context)
    content = (dest / "pyproject.toml").read_text()
    assert 'name = "Test Author"' in content
    assert "email" not in content


def test_license_none_excluded(tmp_path):
    context = {
        "project_name": "no-license",
        "module_name": "no_license",
        "description": "No license project",
        "author_name": "Test",
        "author_email": "test@example.com",
        "python_version": "3.13",
        "license": "None",
    }
    dest = tmp_path / "no-license"
    generate(dest, context)
    content = (dest / "pyproject.toml").read_text()
    assert 'license = "None"' not in content
