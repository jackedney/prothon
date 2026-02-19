"""Tests for project root detection."""

from __future__ import annotations

from prothon.project import find_project_root


def test_find_project_root_from_project_dir(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("project_name: test")
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_from_subdirectory(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("project_name: test")
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) == tmp_path


def test_find_project_root_not_found(tmp_path):
    assert find_project_root(tmp_path) is None
