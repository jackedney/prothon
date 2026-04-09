"""Tests for adoption.py: init_existing workflow and helper functions."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from prothon.adoption import (
    _create_agents_and_links,
    _create_docs,
    _create_workflows,
    _ensure_prothon_ci_section,
    init_existing,
)
from prothon.adoption_templates import (
    _AGENTS_CONTENT,
    _DESIGN_SCAFFOLD,
    _GITLAB_VERSION_BUMP,
    _PATTERNS_SCAFFOLD,
    _SPEC_SCAFFOLD,
    _VERSION_BUMP_WORKFLOW,
    _VERSION_TAG_WORKFLOW,
)
from prothon.exceptions import GitError, ProjectAlreadyInitError, ProthonError
from prothon.git import run_git

from tests.conftest import assert_symlink_to


def _git_project(tmp_path: Path) -> Path:
    """Create a git-initialised directory with a minimal pyproject.toml."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    return tmp_path


# -- init_existing: error paths --


def test_init_existing_fails_when_not_a_git_repo(tmp_path: Path) -> None:
    """init_existing raises GitError outside a git repository."""
    with pytest.raises(GitError, match="not a git repository"):
        init_existing(cwd=tmp_path)


def test_init_existing_fails_when_spec_already_exists(tmp_path: Path) -> None:
    """init_existing raises ProjectAlreadyInitError when SPEC.md exists."""
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Existing spec")
    with pytest.raises(ProjectAlreadyInitError, match="SPEC.md already exists"):
        init_existing(cwd=tmp_path)


def test_init_existing_fails_when_no_pyproject_and_no_data(tmp_path: Path) -> None:
    """init_existing raises ProthonError when Path A has no data."""
    run_git("init", cwd=tmp_path)
    with pytest.raises(ProthonError, match="project details required"):
        init_existing(cwd=tmp_path, data=None)


# -- init_existing: happy path --


def test_init_existing_returns_all_created_paths(tmp_path: Path) -> None:
    """init_existing returns a list containing docs, agents, and skills."""
    root = _git_project(tmp_path)
    created = init_existing(cwd=root)
    for expected in (
        root / "docs" / "SPEC.md",
        root / "docs" / "DESIGN.md",
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / ".agents" / "skills",
    ):
        assert expected in created


def test_init_existing_creates_doc_scaffolds(tmp_path: Path) -> None:
    """init_existing creates SPEC.md, DESIGN.md, and PATTERNS.md with scaffold content."""
    root = _git_project(tmp_path)
    init_existing(cwd=root)
    assert (root / "docs" / "SPEC.md").read_text() == _SPEC_SCAFFOLD
    assert (root / "docs" / "DESIGN.md").read_text() == _DESIGN_SCAFFOLD
    assert (root / "docs" / "PATTERNS.md").read_text() == _PATTERNS_SCAFFOLD


def test_init_existing_creates_agent_files_and_symlinks(tmp_path: Path) -> None:
    """init_existing creates AGENTS.md and CLAUDE/GEMINI/AGENT symlinks."""
    root = _git_project(tmp_path)
    init_existing(cwd=root)
    assert (root / "AGENTS.md").read_text() == _AGENTS_CONTENT
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        assert_symlink_to(root / name, "AGENTS.md")
    assert (root / ".agents" / "skills").is_dir()


def test_init_existing_creates_ci_workflows(tmp_path: Path) -> None:
    """init_existing creates GitHub and GitLab CI workflows."""
    root = _git_project(tmp_path)
    init_existing(cwd=root)
    gh = root / ".github" / "workflows"
    assert (gh / "version-bump.yml").read_text() == _VERSION_BUMP_WORKFLOW
    assert (gh / "version-tag.yml").read_text() == _VERSION_TAG_WORKFLOW
    assert (root / ".gitlab-ci.yml").read_text() == _GITLAB_VERSION_BUMP


def test_init_existing_defaults_cwd(tmp_path: Path) -> None:
    """init_existing defaults to Path.cwd() when cwd is None."""
    _git_project(tmp_path)
    with patch("prothon.adoption.Path.cwd", return_value=tmp_path):
        created = init_existing(cwd=None)
    assert (tmp_path / "docs" / "SPEC.md") in created


def test_init_existing_preserves_existing_workflows(tmp_path: Path) -> None:
    """Existing CI workflows are not overwritten."""
    root = _git_project(tmp_path)
    gh = root / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-bump.yml").write_text("custom")
    init_existing(cwd=root)
    assert (gh / "version-bump.yml").read_text() == "custom"


def test_init_existing_preserves_prothon_ci(tmp_path: Path) -> None:
    """Existing auto_version value is not overwritten."""
    run_git("init", cwd=tmp_path)
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "t"\n\n[tool.prothon.ci]\nauto_version = false\n')
    init_existing(cwd=tmp_path)
    assert "auto_version = false" in p.read_text()


# -- _create_docs --


def test_create_docs_writes_scaffolds_with_gitkeep(tmp_path: Path) -> None:
    """_create_docs writes references/.gitkeep, SPEC.md, DESIGN.md, and PATTERNS.md."""
    created = _create_docs(tmp_path)
    assert len(created) == 4
    assert (tmp_path / "docs" / "references" / ".gitkeep").exists()
    assert (tmp_path / "docs" / "SPEC.md").read_text() == _SPEC_SCAFFOLD
    assert (tmp_path / "docs" / "DESIGN.md").read_text() == _DESIGN_SCAFFOLD


def test_create_docs_skips_existing(tmp_path: Path) -> None:
    """_create_docs does not overwrite existing doc files."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Custom")
    created = _create_docs(tmp_path)
    assert (docs / "SPEC.md") not in created
    assert (docs / "SPEC.md").read_text() == "# Custom"
    assert (docs / "DESIGN.md") in created


def test_create_docs_appends_ast_patterns(tmp_path: Path) -> None:
    """_create_docs writes AST-mined idioms to docs/references/modules.md."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "example.py").write_text("def hello() -> str:\n    return 'hi'\n")
    _create_docs(tmp_path)
    patterns = (tmp_path / "docs" / "PATTERNS.md").read_text()
    assert patterns == _PATTERNS_SCAFFOLD
    modules = (tmp_path / "docs" / "references" / "modules.md").read_text()
    assert "def hello()" in modules


# -- _create_agents_and_links --


def test_create_agents_and_links_full(tmp_path: Path) -> None:
    """Creates AGENTS.md, symlinks, and .agents/skills/ directory."""
    created = _create_agents_and_links(tmp_path)
    assert (tmp_path / "AGENTS.md") in created
    assert (tmp_path / "AGENTS.md").read_text() == _AGENTS_CONTENT
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        assert_symlink_to(tmp_path / name, "AGENTS.md")
    assert (tmp_path / ".agents" / "skills").is_dir()


def test_create_agents_skips_existing(tmp_path: Path) -> None:
    """Does not overwrite existing AGENTS.md or symlinks."""
    (tmp_path / "AGENTS.md").write_text("# Custom")
    os.symlink("AGENTS.md", tmp_path / "CLAUDE.md")
    created = _create_agents_and_links(tmp_path)
    assert (tmp_path / "AGENTS.md") not in created
    assert (tmp_path / "CLAUDE.md") not in created
    assert (tmp_path / "GEMINI.md") in created


# -- _create_workflows --


def test_create_workflows_full(tmp_path: Path) -> None:
    """Creates GitHub workflows and .gitlab-ci.yml."""
    created = _create_workflows(tmp_path)
    gh = tmp_path / ".github" / "workflows"
    assert (gh / "version-bump.yml").read_text() == _VERSION_BUMP_WORKFLOW
    assert (gh / "version-tag.yml").read_text() == _VERSION_TAG_WORKFLOW
    assert (tmp_path / ".gitlab-ci.yml").read_text() == _GITLAB_VERSION_BUMP
    assert len(created) == 3


def test_create_workflows_skips_existing(tmp_path: Path) -> None:
    """Does not overwrite existing workflow files."""
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-bump.yml").write_text("custom")
    created = _create_workflows(tmp_path)
    assert (gh / "version-bump.yml") not in created
    assert (gh / "version-tag.yml") in created


# -- _ensure_prothon_ci_section --


def test_ensure_ci_adds_section(tmp_path: Path) -> None:
    """Adds [tool.prothon.ci] when only [project] exists."""
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "test"\n')
    _ensure_prothon_ci_section(tmp_path)
    content = p.read_text()
    assert "[tool.prothon.ci]" in content
    assert "auto_version = true" in content


def test_ensure_ci_preserves_existing(tmp_path: Path) -> None:
    """Does not overwrite auto_version when already set."""
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "t"\n\n[tool.prothon.ci]\nauto_version = false\n')
    _ensure_prothon_ci_section(tmp_path)
    assert "auto_version = false" in p.read_text()


def test_ensure_ci_noop_without_pyproject(tmp_path: Path) -> None:
    """Does nothing when pyproject.toml does not exist."""
    _ensure_prothon_ci_section(tmp_path)
    assert not (tmp_path / "pyproject.toml").exists()


def test_ensure_ci_creates_nested_tables(tmp_path: Path) -> None:
    """Creates [tool.prothon.ci] alongside existing [tool.ruff]."""
    p = tmp_path / "pyproject.toml"
    p.write_text("[tool.ruff]\nline-length = 88\n")
    _ensure_prothon_ci_section(tmp_path)
    content = p.read_text()
    assert "[tool.prothon.ci]" in content
    assert "line-length = 88" in content
