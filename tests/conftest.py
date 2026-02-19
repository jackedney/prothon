"""Shared test fixtures, fakes, and factories."""

from __future__ import annotations


class FakeGitDiff:
    """Fake GitDiffProvider for testing -- no subprocess calls."""

    def __init__(
        self,
        names: set[str] | None = None,
        stats: dict[str, tuple[int, int]] | None = None,
    ):
        self._names = names or set()
        self._stats = stats or {}

    def diff_names(self, base_commit: str) -> set[str]:
        return self._names

    def diff_numstat(self, base_commit: str) -> dict[str, tuple[int, int]]:
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
