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


# ---------------------------------------------------------------------------
# init_existing: error paths
# ---------------------------------------------------------------------------


class TestInitExistingErrors:
    """Error handling in init_existing()."""

    def test_fails_when_not_a_git_repo(self, tmp_path: Path) -> None:
        """init_existing raises GitError outside a git repository."""
        with pytest.raises(GitError, match="not a git repository"):
            init_existing(cwd=tmp_path)

    def test_fails_when_spec_already_exists(self, tmp_path: Path) -> None:
        """init_existing raises ProjectAlreadyInitError when SPEC.md exists."""
        run_git("init", cwd=tmp_path)
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Existing spec")

        with pytest.raises(ProjectAlreadyInitError, match="SPEC.md already exists"):
            init_existing(cwd=tmp_path)

    def test_fails_when_no_pyproject_and_no_data(self, tmp_path: Path) -> None:
        """init_existing raises ProthonError when Path A has no data."""
        run_git("init", cwd=tmp_path)

        with pytest.raises(ProthonError, match="project details required"):
            init_existing(cwd=tmp_path, data=None)


# ---------------------------------------------------------------------------
# init_existing: happy paths
# ---------------------------------------------------------------------------


class TestInitExistingHappyPath:
    """Successful init_existing invocations (Path B: pyproject.toml present)."""

    @pytest.fixture()
    def git_project(self, tmp_path: Path) -> Path:
        """Create a git-initialised directory with a pyproject.toml."""
        run_git("init", cwd=tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.1.0"\n'
        )
        return tmp_path

    def test_returns_created_paths(self, git_project: Path) -> None:
        """init_existing returns a list of all created file paths."""
        created = init_existing(cwd=git_project)

        assert (git_project / "docs" / "SPEC.md") in created
        assert (git_project / "docs" / "DESIGN.md") in created
        assert (git_project / "docs" / "PATTERNS.md") in created
        assert (git_project / "AGENTS.md") in created
        assert (git_project / "CLAUDE.md") in created
        assert (git_project / "GEMINI.md") in created
        assert (git_project / "AGENT.md") in created
        assert (git_project / ".agents" / "skills") in created

    def test_creates_doc_scaffolds(self, git_project: Path) -> None:
        """init_existing creates SPEC.md, DESIGN.md, and PATTERNS.md."""
        init_existing(cwd=git_project)

        assert (git_project / "docs" / "SPEC.md").read_text() == _SPEC_SCAFFOLD
        assert (git_project / "docs" / "DESIGN.md").read_text() == _DESIGN_SCAFFOLD
        assert (git_project / "docs" / "PATTERNS.md").read_text() == _PATTERNS_SCAFFOLD

    def test_creates_agent_files(self, git_project: Path) -> None:
        """init_existing creates AGENTS.md and symlinks."""
        init_existing(cwd=git_project)

        assert (git_project / "AGENTS.md").read_text() == _AGENTS_CONTENT
        for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
            assert_symlink_to(git_project / name, "AGENTS.md")

    def test_creates_skills_directory(self, git_project: Path) -> None:
        """init_existing creates .agents/skills/ directory."""
        init_existing(cwd=git_project)

        assert (git_project / ".agents" / "skills").is_dir()

    def test_creates_ci_workflows(self, git_project: Path) -> None:
        """init_existing creates GitHub and GitLab CI workflows."""
        init_existing(cwd=git_project)

        gh = git_project / ".github" / "workflows"
        assert (gh / "version-bump.yml").read_text() == _VERSION_BUMP_WORKFLOW
        assert (gh / "version-tag.yml").read_text() == _VERSION_TAG_WORKFLOW
        assert (git_project / ".gitlab-ci.yml").read_text() == _GITLAB_VERSION_BUMP

    def test_adds_prothon_ci_to_pyproject(self, git_project: Path) -> None:
        """init_existing adds [tool.prothon.ci] section to pyproject.toml."""
        init_existing(cwd=git_project)

        content = (git_project / "pyproject.toml").read_text()
        assert "[tool.prothon.ci]" in content
        assert "auto_version = true" in content

    def test_defaults_cwd_to_current_directory(self, tmp_path: Path) -> None:
        """init_existing defaults to cwd when no argument given."""
        run_git("init", cwd=tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "t"\n')

        with patch("prothon.adoption.Path.cwd", return_value=tmp_path):
            created = init_existing(cwd=None)

        assert (tmp_path / "docs" / "SPEC.md") in created


# ---------------------------------------------------------------------------
# init_existing: idempotency / preservation
# ---------------------------------------------------------------------------


class TestInitExistingPreservation:
    """init_existing does not overwrite existing files."""

    @pytest.fixture()
    def git_project(self, tmp_path: Path) -> Path:
        run_git("init", cwd=tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.1.0"\n'
        )
        return tmp_path

    def test_preserves_existing_workflows(self, git_project: Path) -> None:
        """Existing CI workflows are not overwritten."""
        gh = git_project / ".github" / "workflows"
        gh.mkdir(parents=True)
        (gh / "version-bump.yml").write_text("custom bump")
        (git_project / ".gitlab-ci.yml").write_text("custom gitlab")

        init_existing(cwd=git_project)

        assert (gh / "version-bump.yml").read_text() == "custom bump"
        assert (git_project / ".gitlab-ci.yml").read_text() == "custom gitlab"

    def test_preserves_existing_prothon_ci_section(self, git_project: Path) -> None:
        """Existing [tool.prothon.ci] auto_version is not overwritten."""
        pyproject = git_project / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test"\n\n[tool.prothon.ci]\nauto_version = false\n'
        )

        init_existing(cwd=git_project)

        assert "auto_version = false" in pyproject.read_text()


# ---------------------------------------------------------------------------
# _create_docs
# ---------------------------------------------------------------------------


class TestCreateDocs:
    """Tests for the _create_docs helper."""

    def test_creates_three_doc_scaffolds(self, tmp_path: Path) -> None:
        """_create_docs writes SPEC.md, DESIGN.md, and PATTERNS.md."""
        created = _create_docs(tmp_path)

        assert len(created) == 3
        assert (tmp_path / "docs" / "SPEC.md").read_text() == _SPEC_SCAFFOLD
        assert (tmp_path / "docs" / "DESIGN.md").read_text() == _DESIGN_SCAFFOLD
        assert (tmp_path / "docs" / "PATTERNS.md").read_text() == _PATTERNS_SCAFFOLD

    def test_skips_existing_docs(self, tmp_path: Path) -> None:
        """_create_docs does not overwrite existing doc files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "SPEC.md").write_text("# Custom spec")

        created = _create_docs(tmp_path)

        assert (docs / "SPEC.md") not in created
        assert (docs / "SPEC.md").read_text() == "# Custom spec"
        # DESIGN and PATTERNS should still be created
        assert (docs / "DESIGN.md") in created
        assert (docs / "PATTERNS.md") in created

    def test_includes_ast_mined_patterns(self, tmp_path: Path) -> None:
        """_create_docs appends AST-mined idioms to PATTERNS.md."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "example.py").write_text("def hello() -> str:\n    return 'hi'\n")

        _create_docs(tmp_path)

        patterns_text = (tmp_path / "docs" / "PATTERNS.md").read_text()
        assert patterns_text.startswith(_PATTERNS_SCAFFOLD)


# ---------------------------------------------------------------------------
# _create_agents_and_links
# ---------------------------------------------------------------------------


class TestCreateAgentsAndLinks:
    """Tests for the _create_agents_and_links helper."""

    def test_creates_agents_md(self, tmp_path: Path) -> None:
        """_create_agents_and_links writes AGENTS.md with expected content."""
        created = _create_agents_and_links(tmp_path)

        assert (tmp_path / "AGENTS.md") in created
        assert (tmp_path / "AGENTS.md").read_text() == _AGENTS_CONTENT

    def test_creates_symlinks(self, tmp_path: Path) -> None:
        """_create_agents_and_links creates CLAUDE.md, GEMINI.md, AGENT.md symlinks."""
        _create_agents_and_links(tmp_path)

        for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
            assert_symlink_to(tmp_path / name, "AGENTS.md")

    def test_creates_skills_directory(self, tmp_path: Path) -> None:
        """_create_agents_and_links creates .agents/skills/ directory."""
        created = _create_agents_and_links(tmp_path)

        assert (tmp_path / ".agents" / "skills").is_dir()
        assert (tmp_path / ".agents" / "skills") in created

    def test_skips_existing_agents_md(self, tmp_path: Path) -> None:
        """_create_agents_and_links does not overwrite existing AGENTS.md."""
        (tmp_path / "AGENTS.md").write_text("# Custom agents")

        created = _create_agents_and_links(tmp_path)

        assert (tmp_path / "AGENTS.md") not in created
        assert (tmp_path / "AGENTS.md").read_text() == "# Custom agents"

    def test_skips_existing_symlinks(self, tmp_path: Path) -> None:
        """_create_agents_and_links skips symlinks that already exist."""
        (tmp_path / "AGENTS.md").write_text(_AGENTS_CONTENT)
        os.symlink("AGENTS.md", tmp_path / "CLAUDE.md")

        created = _create_agents_and_links(tmp_path)

        assert (tmp_path / "CLAUDE.md") not in created
        # Other symlinks should still be created
        assert (tmp_path / "GEMINI.md") in created
        assert (tmp_path / "AGENT.md") in created


# ---------------------------------------------------------------------------
# _create_workflows
# ---------------------------------------------------------------------------


class TestCreateWorkflows:
    """Tests for the _create_workflows helper."""

    def test_creates_github_workflows(self, tmp_path: Path) -> None:
        """_create_workflows creates version-bump.yml and version-tag.yml."""
        created = _create_workflows(tmp_path)

        gh = tmp_path / ".github" / "workflows"
        assert (gh / "version-bump.yml") in created
        assert (gh / "version-tag.yml") in created
        assert (gh / "version-bump.yml").read_text() == _VERSION_BUMP_WORKFLOW
        assert (gh / "version-tag.yml").read_text() == _VERSION_TAG_WORKFLOW

    def test_creates_gitlab_ci(self, tmp_path: Path) -> None:
        """_create_workflows creates .gitlab-ci.yml."""
        created = _create_workflows(tmp_path)

        assert (tmp_path / ".gitlab-ci.yml") in created
        assert (tmp_path / ".gitlab-ci.yml").read_text() == _GITLAB_VERSION_BUMP

    def test_skips_existing_workflow_files(self, tmp_path: Path) -> None:
        """_create_workflows does not overwrite existing workflow files."""
        gh = tmp_path / ".github" / "workflows"
        gh.mkdir(parents=True)
        (gh / "version-bump.yml").write_text("custom")

        created = _create_workflows(tmp_path)

        assert (gh / "version-bump.yml") not in created
        assert (gh / "version-bump.yml").read_text() == "custom"
        # version-tag.yml should still be created
        assert (gh / "version-tag.yml") in created


# ---------------------------------------------------------------------------
# _ensure_prothon_ci_section
# ---------------------------------------------------------------------------


class TestEnsureProthonCiSection:
    """Tests for the _ensure_prothon_ci_section helper."""

    def test_adds_ci_section_to_bare_pyproject(self, tmp_path: Path) -> None:
        """Adds [tool.prothon.ci] when only [project] exists."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        _ensure_prothon_ci_section(tmp_path)

        content = pyproject.read_text()
        assert "[tool.prothon.ci]" in content
        assert "auto_version = true" in content

    def test_preserves_existing_auto_version(self, tmp_path: Path) -> None:
        """Does not overwrite auto_version when already set."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "t"\n\n[tool.prothon.ci]\nauto_version = false\n'
        )

        _ensure_prothon_ci_section(tmp_path)

        assert "auto_version = false" in pyproject.read_text()

    def test_noop_when_no_pyproject(self, tmp_path: Path) -> None:
        """Does nothing when pyproject.toml does not exist."""
        _ensure_prothon_ci_section(tmp_path)

        assert not (tmp_path / "pyproject.toml").exists()

    def test_creates_nested_tables(self, tmp_path: Path) -> None:
        """Creates [tool], [tool.prothon], [tool.prothon.ci] as needed."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\nline-length = 88\n")

        _ensure_prothon_ci_section(tmp_path)

        content = pyproject.read_text()
        assert "[tool.prothon.ci]" in content
        assert "auto_version = true" in content
        # ruff section should be preserved
        assert "line-length = 88" in content
