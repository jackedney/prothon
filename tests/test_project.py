"""Tests for project root detection."""

from __future__ import annotations

import pytest

from prothon.exceptions import ProjectNotFoundError
from prothon.project import find_project_root


def test_find_project_root_from_project_dir(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec")
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_from_subdirectory(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec")
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) == tmp_path


def test_find_project_root_not_found(tmp_path):
    with pytest.raises(ProjectNotFoundError, match="no prothon project found.*SPEC.md"):
        find_project_root(tmp_path)


def test_find_project_root_ignores_directory_spec(tmp_path):
    """SPEC.md must be a file, not a directory."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").mkdir()  # directory, not file!
    with pytest.raises(ProjectNotFoundError):
        find_project_root(tmp_path)


def test_find_project_root_resolves_to_real_path(tmp_path):
    root = tmp_path / "real"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "SPEC.md").write_text("# Spec")
    link = tmp_path / "link"
    link.symlink_to(root)
    result = find_project_root(link)
    assert result == root.resolve()


def test_find_project_root_error_message_no_xx(tmp_path):
    """Error message must not have 'XX' padding (kills string mutation)."""
    with pytest.raises(ProjectNotFoundError) as exc_info:
        find_project_root(tmp_path)
    assert "XX" not in str(exc_info.value)
