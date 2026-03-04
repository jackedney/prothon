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


def test_py_typed_marker_exists(generated_project):
    """src/{module_name}/py.typed marker file exists."""
    py_typed = generated_project / "src" / "test_project" / "py.typed"
    assert py_typed.exists()


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
        assert_symlink_to(link, "AGENTS.md")


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


def test_ci_workflow_files_generated(generated_project):
    """GitHub Actions, GitLab CI, and pre-commit CI config files are generated."""
    assert (generated_project / ".github" / "workflows" / "ci.yml").exists()
    assert (generated_project / ".gitlab-ci.yml").exists()
    assert (generated_project / ".pre-commit-config.yaml").exists()


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
    """init_existing creates docs, AGENTS.md, symlinks, and skills dir (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
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
    """init_existing returns a list containing all created paths (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
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
        "version-bump.yml",
        ".gitlab-ci.yml",
    }
    created_names = {p.name for p in created}
    assert expected_names == created_names


def test_init_existing_does_not_modify_existing_files(tmp_path):
    """init_existing leaves pre-existing source content untouched."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    init_existing(cwd=tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    assert "[tool.ruff]" in content
    assert "line-length = 88" in content


def test_init_existing_spec_scaffold_has_required_sections(tmp_path):
    """Scaffolded SPEC.md contains all required section headings (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)
    content = (tmp_path / "docs" / "SPEC.md").read_text()
    assert "## Purpose" in content
    assert "## Requirements" in content
    assert "## Constraints" in content
    assert "## Out of Scope" in content


def test_init_existing_design_scaffold_has_sections(tmp_path):
    """Scaffolded DESIGN.md has required sections (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)
    content = (tmp_path / "docs" / "DESIGN.md").read_text()
    assert "## Architecture" in content
    assert "## Technology Choices" in content


def test_init_existing_patterns_scaffold_has_sections(tmp_path):
    """Scaffolded PATTERNS.md has required sections (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)
    content = (tmp_path / "docs" / "PATTERNS.md").read_text()
    assert "## Code Organization" in content
    assert "## Testing Patterns" in content


def test_init_existing_agents_md_content(tmp_path):
    """AGENTS.md has doc hierarchy content (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "Documentation Hierarchy" in content
    assert "SPEC.md" in content


def test_init_existing_symlinks_point_to_agents_md(tmp_path):
    """Symlinks created by init_existing point to AGENTS.md (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = tmp_path / name
        assert os.readlink(str(link)) == "AGENTS.md"


def test_init_existing_replaces_existing_symlinks(tmp_path):
    """Existing symlinks are replaced (not duplicated) (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    # Create initial symlinks pointing elsewhere
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = tmp_path / name
        os.symlink("nonexistent", link)
    init_existing(cwd=tmp_path)
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = tmp_path / name
        assert os.readlink(str(link)) == "AGENTS.md"


def test_init_existing_uses_cwd_when_none(tmp_path, monkeypatch):
    """init_existing defaults to cwd when cwd arg is None (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    monkeypatch.chdir(tmp_path)
    created = init_existing(cwd=None)
    assert len(created) > 0
    assert (tmp_path / "docs" / "SPEC.md").exists()


def test_template_dir_returns_dir_with_copier_yml():
    """_template_dir returns a directory containing copier.yml."""
    result = _template_dir()
    assert result.is_dir()
    assert (result / "copier.yml").exists()


# --- _template_dir error path ---


def test_template_dir_raises_when_not_found(tmp_path, monkeypatch):
    """_template_dir raises FileNotFoundError with correct message when template missing."""
    import prothon.scaffold

    monkeypatch.setattr(prothon.scaffold, "__file__", str(tmp_path / "scaffold.py"))
    with pytest.raises(FileNotFoundError, match="^Cannot locate template directory$"):
        _template_dir()


# --- generate copier args ---


def test_generate_copier_kwargs_exact(tmp_path):
    """Verify all kwargs passed to copier.run_copy (kills arg mutations)."""
    from unittest.mock import MagicMock, patch

    dest = tmp_path / "project"
    data = {"module_name": "m"}

    mock_run_copy = MagicMock()
    with patch("copier.run_copy", mock_run_copy):
        with patch("prothon.scaffold._post_generate"):
            generate(dest, data)

    mock_run_copy.assert_called_once()
    kw = mock_run_copy.call_args.kwargs
    assert kw["data"] is data
    assert kw["defaults"] is True  # bool(data) where data is truthy
    assert kw["unsafe"] is True
    assert kw["vcs_ref"] == "HEAD"


def test_generate_copier_defaults_false_when_no_data(tmp_path):
    """defaults=bool(None) → False when data is None."""
    from unittest.mock import MagicMock, patch

    dest = tmp_path / "project"
    mock_run_copy = MagicMock()
    with patch("copier.run_copy", mock_run_copy):
        with patch("prothon.scaffold._post_generate"):
            generate(dest, None)

    kw = mock_run_copy.call_args.kwargs
    assert kw["defaults"] is False  # bool(None) = False


# --- _post_generate idempotency ---


def test_post_generate_agents_skills_exist_ok(tmp_path, scaffold_data):
    """Calling generate on a dest where .agents/skills already exists must not crash."""
    from unittest.mock import patch
    from prothon.scaffold import _post_generate

    dest = tmp_path / "test-project"
    generate(dest, data=scaffold_data)
    # .agents/skills now exists from first generate call
    assert (dest / ".agents" / "skills").is_dir()

    # Calling _post_generate again should NOT raise (exist_ok=True is needed)
    # Mock git operations since repo is clean
    with patch("prothon.scaffold.run_git"):
        _post_generate(dest)
    assert (dest / ".agents" / "skills").is_dir()


# --- _post_generate commit message ---


def test_post_generate_commit_message(generated_project):
    """Git commit message must be exact (kills string case mutations)."""
    import subprocess

    result = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        capture_output=True,
        text=True,
        cwd=generated_project,
    )
    assert result.stdout.strip() == "Initial commit from prothon template"


# --- init_existing with pre-existing dirs ---


def test_init_existing_with_preexisting_docs_dir(tmp_path):
    """init_existing succeeds when docs/ already exists (exist_ok=True needed) (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "docs").mkdir()  # docs/ exists but no SPEC.md

    init_existing(cwd=tmp_path)

    assert (tmp_path / "docs" / "SPEC.md").exists()
    assert (tmp_path / "docs" / "DESIGN.md").exists()


def test_init_existing_with_preexisting_agents_skills_dir(tmp_path):
    """init_existing succeeds when .agents/skills/ already exists (exist_ok=True needed) (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    init_existing(cwd=tmp_path)

    assert (tmp_path / ".agents" / "skills").is_dir()
    assert (tmp_path / "docs" / "SPEC.md").exists()


# --- init_existing Path A (no pyproject.toml) ---


def test_init_existing_path_a_calls_copier(tmp_path):
    """Path A: when pyproject.toml absent, copier.run_copy is called with correct args."""
    from unittest.mock import MagicMock, patch

    run_git("init", cwd=tmp_path)

    mock_run_copy = MagicMock()
    with patch("copier.run_copy", mock_run_copy):
        with patch(
            "prothon.scaffold._collect_project_details",
            return_value={
                "module_name": "testmod",
                "description": "test desc",
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "python_version": "3.12",
                "license": "MIT",
            },
        ):
            init_existing(cwd=tmp_path)

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


def test_init_existing_path_a_creates_common_overlay(tmp_path):
    """Path A: common overlay (docs, AGENTS.md, symlinks, skills) still created."""
    from unittest.mock import patch

    run_git("init", cwd=tmp_path)

    with patch("copier.run_copy"):
        with patch(
            "prothon.scaffold._collect_project_details",
            return_value={
                "module_name": "testmod",
                "description": "test",
                "author_name": "Test",
                "author_email": "test@example.com",
                "python_version": "3.12",
                "license": "MIT",
            },
        ):
            init_existing(cwd=tmp_path)

    assert (tmp_path / "docs" / "SPEC.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".agents" / "skills").is_dir()
    assert_symlink_to(tmp_path / "CLAUDE.md", "AGENTS.md")


def test_init_existing_path_b_skips_copier(tmp_path):
    """Path B: when pyproject.toml present, copier.run_copy is NOT called."""
    from unittest.mock import MagicMock, patch

    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    mock_run_copy = MagicMock()
    with patch("copier.run_copy", mock_run_copy):
        init_existing(cwd=tmp_path)

    mock_run_copy.assert_not_called()


# --- generate: template rendering edge cases ---


def test_generate_strips_jinja_suffix(generated_project):
    """Rendered files have .jinja suffix stripped."""
    assert (generated_project / "pyproject.toml").exists()
    assert not (generated_project / "pyproject.toml.jinja").exists()


def test_generate_templates_directory_paths(generated_project):
    """Module __init__.py rendered at src/{module_name}/ with description."""
    init = generated_project / "src" / "test_project" / "__init__.py"
    assert init.exists()
    assert '"A test project"' in init.read_text()


def test_generate_writes_copier_answers(generated_project):
    """.copier-answers.yml contains the rendered module_name value."""
    answers = generated_project / ".copier-answers.yml"
    assert answers.exists()
    content = answers.read_text()
    assert "module_name: test_project" in content


def test_generate_skips_copier_answers_template(generated_project):
    """No _copier_conf file left in generated output."""
    for p in generated_project.rglob("*"):
        assert "_copier_conf" not in p.name


def test_generate_authors_omitted_when_both_empty(tmp_path):
    """authors section omitted from pyproject.toml when name and email empty."""
    data = {
        "project_name": "no-author",
        "module_name": "no_author",
        "description": "No author project",
        "author_name": "",
        "author_email": "",
        "python_version": "3.13",
        "license": "MIT",
    }
    dest = tmp_path / "no-author"
    generate(dest, data)
    content = (dest / "pyproject.toml").read_text()
    assert "authors" not in content


def test_generate_authors_name_only(tmp_path):
    """authors section contains name but no email when email is empty."""
    data = {
        "project_name": "name-only",
        "module_name": "name_only",
        "description": "Name only project",
        "author_name": "Test Author",
        "author_email": "",
        "python_version": "3.13",
        "license": "MIT",
    }
    dest = tmp_path / "name-only"
    generate(dest, data)
    content = (dest / "pyproject.toml").read_text()
    assert 'name = "Test Author"' in content
    assert "email" not in content


def test_generate_license_none_excluded(tmp_path):
    """license = "None" is excluded from pyproject.toml."""
    data = {
        "project_name": "no-license",
        "module_name": "no_license",
        "description": "No license project",
        "author_name": "Test",
        "author_email": "test@example.com",
        "python_version": "3.13",
        "license": "None",
    }
    dest = tmp_path / "no-license"
    generate(dest, data)
    content = (dest / "pyproject.toml").read_text()
    assert 'license = "None"' not in content


# --- init_existing: version-bump CI workflow ---


def test_init_existing_creates_version_bump_workflow(tmp_path):
    """init_existing creates .github/workflows/version-bump.yml (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)

    workflow = tmp_path / ".github" / "workflows" / "version-bump.yml"
    assert workflow.exists()


def test_init_existing_version_bump_workflow_content(tmp_path):
    """version-bump.yml triggers on main and has version-bump job."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)

    content = (tmp_path / ".github" / "workflows" / "version-bump.yml").read_text()
    assert "branches: [main]" in content
    assert "version-bump:" in content
    assert "name: Version Bump" in content


def test_init_existing_appends_prothon_ci_to_pyproject(tmp_path):
    """init_existing appends [tool.prothon.ci] to pyproject.toml (Path B)."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    init_existing(cwd=tmp_path)

    content = (tmp_path / "pyproject.toml").read_text()
    assert "[tool.prothon.ci]" in content
    assert "auto_version = true" in content


def test_init_existing_does_not_overwrite_existing_prothon_ci(tmp_path):
    """init_existing does NOT modify pyproject.toml if [tool.prothon.ci] exists."""
    run_git("init", cwd=tmp_path)
    original = "[project]\nname = 'test'\n\n[tool.prothon.ci]\nauto_version = false\n"
    (tmp_path / "pyproject.toml").write_text(original)
    init_existing(cwd=tmp_path)

    content = (tmp_path / "pyproject.toml").read_text()
    assert "auto_version = false" in content
    # Should not have duplicate sections
    assert content.count("[tool.prothon.ci]") == 1


def test_init_existing_creates_workflow_without_pyproject(tmp_path):
    """init_existing creates version-bump.yml even when pyproject.toml absent (Path A)."""
    from unittest.mock import patch

    run_git("init", cwd=tmp_path)

    with patch("copier.run_copy"):
        with patch(
            "prothon.scaffold._collect_project_details",
            return_value={
                "module_name": "testmod",
                "description": "test",
                "author_name": "Test",
                "author_email": "test@example.com",
                "python_version": "3.12",
                "license": "MIT",
            },
        ):
            init_existing(cwd=tmp_path)

    workflow = tmp_path / ".github" / "workflows" / "version-bump.yml"
    assert workflow.exists()


def test_init_existing_skips_existing_workflow(tmp_path):
    """init_existing does not overwrite pre-existing version-bump.yml."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "version-bump.yml").write_text("# custom workflow\n")

    init_existing(cwd=tmp_path)

    content = (workflow_dir / "version-bump.yml").read_text()
    assert content == "# custom workflow\n"


def test_init_existing_creates_gitlab_ci(tmp_path):
    """init_existing creates .gitlab-ci.yml with version-bump job."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    init_existing(cwd=tmp_path)

    gitlab_ci = tmp_path / ".gitlab-ci.yml"
    assert gitlab_ci.exists()
    content = gitlab_ci.read_text()
    assert "version-bump" in content
    assert "CI_COMMIT_BRANCH" in content


def test_init_existing_skips_existing_gitlab_ci(tmp_path):
    """init_existing does not overwrite pre-existing .gitlab-ci.yml."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / ".gitlab-ci.yml").write_text("# existing ci config\n")

    init_existing(cwd=tmp_path)

    content = (tmp_path / ".gitlab-ci.yml").read_text()
    assert content == "# existing ci config\n"
