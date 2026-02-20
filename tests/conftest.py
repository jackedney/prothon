"""Shared test fixtures, fakes, and factories."""

from __future__ import annotations

from pathlib import Path

from prothon.git import DiffStat


class FakeGitDiff:
    """Fake GitDiffProvider for testing -- no subprocess calls."""

    def __init__(
        self,
        names: set[str] | None = None,
        stats: DiffStat | None = None,
    ):
        self._names = names or set()
        self._stats = stats or {}

    def diff_names(self, base_commit: str) -> set[str]:
        return self._names

    def diff_numstat(self, base_commit: str) -> DiffStat:
        return self._stats


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
    }
    return {**base, **overrides}


def assert_symlink_to(link: Path, target_name: str) -> None:
    """Assert that link is a symlink pointing to target_name."""
    assert link.is_symlink(), f"{link} is not a symlink"
    actual = str(link.readlink())
    assert actual == target_name, f"{link} points to {actual}, expected {target_name}"
