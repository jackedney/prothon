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
    with pytest.raises(ProjectNotFoundError, match="no prothon project found"):
        find_project_root(tmp_path)
