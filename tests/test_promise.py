"""Tests for the change promise checker."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from prothon.exceptions import PromiseError
from prothon.promise import (
    CheckResult,
    Metadata,
    Promise,
    Task,
    TaskCheckReport,
    _within_tolerance,
    check_task,
    cleanup,
    complete_task,
    load_promise,
    plan,
    save_promise,
    status,
)

from tests.conftest import FakeGitDiff, make_task

SAMPLE_PROMISE = Promise(
    metadata=Metadata(base_commit="abc1234"),
    tasks=[
        Task(
            title="Add auth module",
            success_criteria="JWT middleware works",
            files_to_modify=["src/app.py"],
            files_to_create=["src/auth.py", "tests/test_auth.py"],
            files_to_remove=["src/old_auth.py"],
            expected_lines_added=100,
            expected_lines_removed=20,
        ),
        Task(
            title="Add config loading",
            success_criteria="Config loads from env vars",
            files_to_create=["src/config.py"],
            expected_lines_added=30,
        ),
    ],
)


@pytest.fixture
def promise_file(tmp_path: Path) -> Path:
    p = tmp_path / "change_promise.toml"
    save_promise(SAMPLE_PROMISE, p)
    return p


class TestWithinTolerance:
    """Tests for _within_tolerance with +/-30%/+/-30 tolerance."""

    def test_exact_match(self):
        assert _within_tolerance(100, 100) is True

    def test_at_thirty_percent_upper(self):
        # 100 + 30% = 130
        assert _within_tolerance(100, 130) is True

    def test_over_thirty_percent_upper(self):
        assert _within_tolerance(100, 131) is False

    def test_at_thirty_percent_lower(self):
        # 100 - 30% = 70
        assert _within_tolerance(100, 70) is True

    def test_under_thirty_percent_lower(self):
        assert _within_tolerance(100, 69) is False

    def test_absolute_floor_when_small_expected(self):
        # 10 expected, 30% = 3, but absolute minimum is 30
        # So tolerance is 30: range is -20 to 40
        assert _within_tolerance(10, 40) is True
        assert _within_tolerance(10, 41) is False

    def test_zero_expected_uses_absolute(self):
        # 0 expected, 30% = 0, absolute = 30
        assert _within_tolerance(0, 30) is True
        assert _within_tolerance(0, 31) is False

    @given(expected=st.integers(min_value=0, max_value=10_000))
    def test_symmetry_exact_match_always_passes(self, expected: int):
        """Hypothesis: exact match always passes regardless of expected value."""
        assert _within_tolerance(expected, expected) is True

    @given(
        expected=st.integers(min_value=0, max_value=10_000),
        delta=st.integers(min_value=0, max_value=100_000),
    )
    def test_tolerance_is_symmetric(self, expected: int, delta: int):
        """Hypothesis: tolerance is symmetric -- +delta and -delta give same result."""
        above = _within_tolerance(expected, expected + delta)
        below = _within_tolerance(expected, expected - delta)
        assert above == below


class TestLoadSaveRoundtrip:
    def test_roundtrip(self, promise_file: Path):
        promise = load_promise(promise_file)
        assert promise.tasks[0].title == "Add auth module"
        assert len(promise.tasks) == 2

        promise.tasks[0].completed = True
        save_promise(promise, promise_file)

        reloaded = load_promise(promise_file)
        assert reloaded.tasks[0].completed is True
        assert reloaded.tasks[1].completed is False

    def test_roundtrip_preserves_metadata(self, promise_file: Path):
        promise = load_promise(promise_file)
        assert promise.metadata.base_commit == "abc1234"

        save_promise(promise, promise_file)
        reloaded = load_promise(promise_file)
        assert reloaded.metadata.base_commit == "abc1234"


class TestCheckTask:
    def test_all_pass(self, promise_file: Path, tmp_path: Path):
        """All files exist/modified/removed, line counts in tolerance."""
        # Create the files that should exist
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "auth.py").write_text("auth code")
        (tmp_path / "tests" / "test_auth.py").write_text("test code")
        # src/old_auth.py should NOT exist (it's in files_to_remove)

        # Update file paths to be relative to tmp_path
        promise = load_promise(promise_file)
        promise.tasks[0].files_to_create = [
            str(tmp_path / "src" / "auth.py"),
            str(tmp_path / "tests" / "test_auth.py"),
        ]
        promise.tasks[0].files_to_remove = [
            str(tmp_path / "src" / "old_auth.py"),
        ]
        save_promise(promise, promise_file)

        fake_diff = FakeGitDiff(
            names={"src/app.py"},
            stats={
                "src/app.py": (10, 15),
                str(tmp_path / "src" / "auth.py"): (80, 0),
                str(tmp_path / "tests" / "test_auth.py"): (25, 0),
            },
        )
        report = check_task(0, diff=fake_diff, path=promise_file)
        assert report.passed is True
        assert all(c.passed for c in report.checks)

    def test_missing_created_file(self, promise_file: Path, tmp_path: Path):
        """Fail when a file that should be created doesn't exist."""
        promise = load_promise(promise_file)
        promise.tasks[0].files_to_create = [
            str(tmp_path / "src" / "auth.py"),  # doesn't exist
        ]
        promise.tasks[0].files_to_remove = []
        save_promise(promise, promise_file)

        fake_diff = FakeGitDiff(names={"src/app.py"})
        report = check_task(0, diff=fake_diff, path=promise_file)
        create_check = next(c for c in report.checks if c.name == "files_to_create")
        assert create_check.passed is False

    def test_unmodified_file(self, promise_file: Path):
        """Fail when a file that should be modified isn't in git diff."""
        fake_diff = FakeGitDiff(names=set())  # nothing modified
        report = check_task(0, diff=fake_diff, path=promise_file)
        modify_check = next(c for c in report.checks if c.name == "files_to_modify")
        assert modify_check.passed is False

    def test_file_not_removed(self, promise_file: Path, tmp_path: Path):
        """Fail when a file that should be removed still exists."""
        (tmp_path / "old_auth.py").write_text("old code")
        promise = load_promise(promise_file)
        promise.tasks[0].files_to_remove = [str(tmp_path / "old_auth.py")]
        save_promise(promise, promise_file)

        fake_diff = FakeGitDiff(names={"src/app.py"})
        report = check_task(0, diff=fake_diff, path=promise_file)
        remove_check = next(c for c in report.checks if c.name == "files_to_remove")
        assert remove_check.passed is False

    def test_line_count_outside_tolerance(self, promise_file: Path):
        """Fail when line counts are way off."""
        fake_diff = FakeGitDiff(
            names={"src/app.py"},
            stats={"src/app.py": (5, 200)},  # 200 removed vs 20 expected
        )
        report = check_task(0, diff=fake_diff, path=promise_file)
        removed_check = next(
            (c for c in report.checks if c.name == "lines_removed"), None
        )
        if removed_check:
            assert removed_check.passed is False

    def test_index_out_of_range(self, promise_file: Path):
        fake_diff = FakeGitDiff()
        with pytest.raises(PromiseError):
            check_task(99, diff=fake_diff, path=promise_file)

    def test_empty_file_lists_skip_checks(self, promise_file: Path):
        """Tasks with empty file lists should skip those checks."""
        fake_diff = FakeGitDiff()
        report = check_task(
            1, diff=fake_diff, path=promise_file
        )  # task 1 has no modify/remove
        check_names = [c.name for c in report.checks]
        assert "files_to_modify" not in check_names
        assert "files_to_remove" not in check_names


class TestCheckTaskReadsBaseCommit:
    """Tests that check_task uses base_commit from promise metadata."""

    def test_passes_base_commit_to_diff_provider(self, tmp_path: Path):
        promise = Promise(
            metadata=Metadata(base_commit="abc1234"),
            tasks=[
                Task(
                    title="Test task",
                    files_to_modify=["src/app.py"],
                    expected_lines_added=50,
                    expected_lines_removed=5,
                ),
            ],
        )
        promise_path = tmp_path / "promise.toml"
        save_promise(promise, promise_path)

        # Capture which base_commit is passed to the fake
        captured_commits: list[str] = []

        class CapturingFakeDiff:
            def diff_names(self, base_commit: str) -> set[str]:
                captured_commits.append(base_commit)
                return {"src/app.py"}

            def diff_numstat(self, base_commit: str) -> dict[str, tuple[int, int]]:
                captured_commits.append(base_commit)
                return {"src/app.py": (50, 5)}

        check_task(0, diff=CapturingFakeDiff(), path=promise_path)
        assert all(c == "abc1234" for c in captured_commits)


class TestCompleteTask:
    def test_marks_completed(self, promise_file: Path):
        complete_task(0, path=promise_file)
        promise = load_promise(promise_file)
        assert promise.tasks[0].completed is True
        assert promise.tasks[1].completed is False

    def test_index_out_of_range(self, promise_file: Path):
        with pytest.raises(PromiseError):
            complete_task(99, path=promise_file)

    def test_marks_complete_and_records_attempts(self, tmp_path: Path):
        promise = Promise(
            metadata=Metadata(base_commit="abc1234"),
            tasks=[Task(title="Test")],
        )
        p = tmp_path / "promise.toml"
        save_promise(promise, p)

        complete_task(0, attempts=3, path=p)

        result = load_promise(p)
        assert result.tasks[0].completed is True
        assert result.tasks[0].attempts == 3

    def test_defaults_to_one_attempt(self, tmp_path: Path):
        promise = Promise(
            metadata=Metadata(base_commit="abc1234"),
            tasks=[Task(title="Test")],
        )
        p = tmp_path / "promise.toml"
        save_promise(promise, p)

        complete_task(0, path=p)

        result = load_promise(p)
        assert result.tasks[0].attempts == 1


class TestStatus:
    def test_shows_all_tasks(self, promise_file: Path):
        output = status(promise_file)
        assert "Add auth module" in output
        assert "Add config loading" in output
        assert "0/2 completed" in output

    def test_reflects_completion(self, promise_file: Path):
        complete_task(0, path=promise_file)
        output = status(promise_file)
        assert "1/2 completed" in output


class TestReportFormat:
    def test_format_pass(self):
        report = TaskCheckReport(
            task_index=0,
            title="Test task",
            checks=[
                CheckResult(name="files_to_create", passed=True, detail="2/2 exist"),
            ],
        )
        formatted = report.format()
        assert "PASS" in formatted
        assert "DISCREPANCY" not in formatted

    def test_format_discrepancy(self):
        report = TaskCheckReport(
            task_index=0,
            title="Test task",
            checks=[
                CheckResult(name="files_to_create", passed=True, detail="2/2 exist"),
                CheckResult(
                    name="files_to_modify", passed=False, detail="0/1 modified"
                ),
            ],
        )
        formatted = report.format()
        assert "DISCREPANCY" in formatted
        assert "1 failure" in formatted


class TestPlan:
    """Tests for plan pretty-print function."""

    def test_formats_single_task(self, tmp_path: Path):
        promise = Promise(
            metadata=Metadata(base_commit="abc1234", created_at="2026-02-18T14:30:00"),
            tasks=[
                Task(
                    title="Add auth middleware",
                    goal="JWT validation on all protected routes",
                    success_criteria="401 without token",
                    files_to_create=["src/auth.py", "tests/test_auth.py"],
                    files_to_modify=["src/app.py"],
                    context_files=["src/middleware.py"],
                    doc_sections=["DESIGN.md#Auth"],
                    reference_skills=["tech-fastapi"],
                    expected_lines_added=120,
                    expected_lines_removed=5,
                ),
            ],
        )
        p = tmp_path / "promise.toml"
        save_promise(promise, p)

        output = plan(p)
        assert "PLAN: 1 task" in output
        assert "base: abc1234" in output
        assert "Task 0: Add auth middleware" in output
        assert "JWT validation" in output
        assert "src/auth.py" in output
        assert "src/app.py" in output
        assert "src/middleware.py" in output
        assert "tech-fastapi" in output
        assert "DESIGN.md#Auth" in output
        assert "+120 / -5" in output

    def test_formats_dependencies(self, tmp_path: Path):
        promise = Promise(
            metadata=Metadata(base_commit="abc1234"),
            tasks=[
                Task(
                    title="Task A",
                    goal="First",
                    expected_lines_added=10,
                ),
                Task(
                    title="Task B",
                    goal="Second",
                    dependencies=[0],
                    expected_lines_added=20,
                ),
            ],
        )
        p = tmp_path / "promise.toml"
        save_promise(promise, p)

        output = plan(p)
        assert "PLAN: 2 tasks" in output
        assert "Task 0" in output
        assert "Task 1" in output
        assert "Deps:   Task 0" in output


class TestCleanup:
    """Tests for cleanup (removing the promise file)."""

    def test_removes_promise_file(self, tmp_path: Path):
        p = tmp_path / "promise.toml"
        save_promise(Promise(), p)
        assert p.exists()

        cleanup(p)
        assert not p.exists()

    def test_raises_if_file_missing(self, tmp_path: Path):
        p = tmp_path / "promise.toml"
        with pytest.raises(FileNotFoundError):
            cleanup(p)


class TestMakeTaskFactory:
    """Tests for the make_task test factory."""

    def test_defaults(self):
        task_dict = make_task()
        assert task_dict["title"] == "test task"
        assert task_dict["expected_lines_added"] == 50
        assert task_dict["completed"] is False

    def test_overrides(self):
        task_dict = make_task(title="custom", expected_lines_added=200, completed=True)
        assert task_dict["title"] == "custom"
        assert task_dict["expected_lines_added"] == 200
        assert task_dict["completed"] is True
