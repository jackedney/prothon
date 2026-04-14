"""Shared test fixtures, fakes, and factories."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from prothon.git import DiffStat
from prothon.scaffold import generate


class FakeGitDiff:
    """Fake GitDiffProvider for testing -- no subprocess calls."""

    def __init__(
        self,
        names: set[str] | None = None,
        stats: DiffStat | None = None,
    ):
        self._names = names or set()
        self._stats = stats or {}
        self.last_diff_names_paths: tuple[str, ...] = ()
        self.last_diff_numstat_paths: tuple[str, ...] = ()

    def diff_names(self, base_commit: str, *paths: str) -> set[str]:
        self.last_diff_names_paths = paths
        if not paths:
            return self._names
        return {n for n in self._names if n in paths}

    def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat:
        self.last_diff_numstat_paths = paths
        if not paths:
            return self._stats
        return {k: v for k, v in self._stats.items() if k in paths}


@pytest.fixture(scope="module")
def shared_project(tmp_path_factory):
    """Generate a Copier project once, copy for tests that only need a valid root."""
    dest = tmp_path_factory.mktemp("shared") / "test-project"
    generate(
        dest,
        {
            "project_name": "test-project",
            "module_name": "test_project",
            "description": "A test project",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "python_version": "3.13",
            "license": "MIT",
        },
    )
    return dest


@pytest.fixture
def project_copy(shared_project, tmp_path):
    """Fast per-test copy of the shared generated project."""
    dest = tmp_path / "test-project"
    shutil.copytree(shared_project, dest, symlinks=True)
    return dest


def make_task(
    title: str = "test task",
    files_to_create: list[str] | None = None,
    expected_lines_added: int = 50,
    **overrides: object,
) -> dict:
    """Build a task dict with sensible defaults for tests."""
    base: dict = {
        "title": title,
        "goal": "",
        "success_criteria": "",
        "files_to_create": files_to_create or [],
        "files_to_modify": [],
        "files_to_remove": [],
        "expected_lines_added": expected_lines_added,
        "expected_lines_removed": 0,
        "context_files": [],
        "doc_sections": [],
        "reference_skills": [],
        "dependencies": [],
        "completed": False,
        "attempts": 0,
        "max_attempts": 3,
    }
    return {**base, **overrides}


def assert_symlink_to(link: Path, target_name: str) -> None:
    """Assert that link is a symlink pointing to target_name."""
    assert link.is_symlink(), f"{link} is not a symlink"
    actual = str(link.readlink())
    assert actual == target_name, f"{link} points to {actual}, expected {target_name}"
