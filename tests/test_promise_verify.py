"""Tests for promise_verify.py -- verification checks and tolerance logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from prothon.compliance import CheckStatus
from prothon.exceptions import PromiseError
from prothon.models import Metadata, Promise, Task
from prothon.promise import save_promise
from prothon.promise_verify import (
    _check_files_to_create,
    _check_files_to_modify,
    _check_files_to_remove,
    _check_line_counts,
    _validate_params,
    _within_tolerance,
    check_task,
)

from tests.conftest import FakeGitDiff


@pytest.fixture(autouse=True)
def mock_pre_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock pre-commit execution for all tests to avoid environment dependencies."""
    monkeypatch.setattr(
        "prothon.promise_verify.run_pre_commit", lambda _p, **_k: (0, "Passed")
    )


# ---------------------------------------------------------------------------
# Helper to build a Promise with tasks
# ---------------------------------------------------------------------------


def _promise_with_tasks(*tasks: Task) -> Promise:
    return Promise(metadata=Metadata(base_commit="abc1234"), tasks=list(tasks))


# ===========================================================================
# _within_tolerance
# ===========================================================================


class TestWithinTolerance:
    """Boundary tests for the +/-30% or +/-30 line tolerance rule."""

    def test_exact_match(self) -> None:
        assert _within_tolerance(100, 100) is True

    # --- percentage-based (expected=100 -> tolerance=30) ---

    def test_upper_boundary_pass(self) -> None:
        assert _within_tolerance(100, 130) is True

    def test_upper_boundary_fail(self) -> None:
        assert _within_tolerance(100, 131) is False

    def test_lower_boundary_pass(self) -> None:
        assert _within_tolerance(100, 70) is True

    def test_lower_boundary_fail(self) -> None:
        assert _within_tolerance(100, 69) is False

    # --- absolute floor kicks in for small expected values ---

    def test_absolute_floor_upper_pass(self) -> None:
        # expected=10, 30%=3, abs=30 -> tolerance=30; 10+30=40
        assert _within_tolerance(10, 40) is True

    def test_absolute_floor_upper_fail(self) -> None:
        assert _within_tolerance(10, 41) is False

    def test_absolute_floor_lower_pass(self) -> None:
        # 10 - 30 = -20, actual=0 is within range
        assert _within_tolerance(10, 0) is True

    def test_absolute_floor_lower_fail(self) -> None:
        # 10 - 30 = -20, but actual can't be negative in practice;
        # test the boundary at distance 31
        assert _within_tolerance(10, 41) is False

    def test_zero_expected_within_absolute(self) -> None:
        # expected=0, 30%=0, abs=30 -> tolerance=30
        assert _within_tolerance(0, 30) is True

    def test_zero_expected_outside_absolute(self) -> None:
        assert _within_tolerance(0, 31) is False

    def test_large_expected_uses_percentage(self) -> None:
        # expected=200, 30%=60, abs=30 -> tolerance=60
        assert _within_tolerance(200, 260) is True
        assert _within_tolerance(200, 261) is False


# ===========================================================================
# _check_files_to_create
# ===========================================================================


class TestCheckFilesToCreate:
    """Verify existence checks for files declared as 'to create'."""

    def test_empty_list_skipped(self) -> None:
        task = Task(title="t")
        result = _check_files_to_create(task, Path("/tmp"))
        assert result.status is CheckStatus.SKIP

    def test_all_exist_passed(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        task = Task(title="t", files_to_create=["a.py", "b.py"])
        result = _check_files_to_create(task, tmp_path)
        assert result.status is CheckStatus.PASS
        assert "2/2" in result.detail

    def test_partial_exist_failed(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x")
        task = Task(title="t", files_to_create=["a.py", "missing.py"])
        result = _check_files_to_create(task, tmp_path)
        assert result.status is CheckStatus.FAIL
        assert "1/2" in result.detail

    def test_none_exist_failed(self, tmp_path: Path) -> None:
        task = Task(title="t", files_to_create=["nope.py"])
        result = _check_files_to_create(task, tmp_path)
        assert result.status is CheckStatus.FAIL
        assert "0/1" in result.detail


# ===========================================================================
# _check_files_to_modify
# ===========================================================================


class TestCheckFilesToModify:
    """Verify that declared modifications appear in the git diff."""

    def test_empty_list_skipped(self) -> None:
        task = Task(title="t")
        diff = FakeGitDiff()
        result = _check_files_to_modify(task, diff, "HEAD")
        assert result.status is CheckStatus.SKIP

    def test_all_in_diff_passed(self) -> None:
        task = Task(title="t", files_to_modify=["src/a.py", "src/b.py"])
        diff = FakeGitDiff(names={"src/a.py", "src/b.py"})
        result = _check_files_to_modify(task, diff, "HEAD")
        assert result.status is CheckStatus.PASS
        assert "2/2" in result.detail

    def test_partial_in_diff_failed(self) -> None:
        task = Task(title="t", files_to_modify=["src/a.py", "src/b.py"])
        diff = FakeGitDiff(names={"src/a.py"})
        result = _check_files_to_modify(task, diff, "HEAD")
        assert result.status is CheckStatus.FAIL
        assert "1/2" in result.detail

    def test_none_in_diff_failed(self) -> None:
        task = Task(title="t", files_to_modify=["src/a.py"])
        diff = FakeGitDiff(names=set())
        result = _check_files_to_modify(task, diff, "HEAD")
        assert result.status is CheckStatus.FAIL
        assert "0/1" in result.detail


# ===========================================================================
# _check_files_to_remove
# ===========================================================================


class TestCheckFilesToRemove:
    """Verify that declared removals no longer exist on disk."""

    def test_empty_list_skipped(self, tmp_path: Path) -> None:
        task = Task(title="t")
        result = _check_files_to_remove(task, tmp_path)
        assert result.status is CheckStatus.SKIP

    def test_all_removed_passed(self, tmp_path: Path) -> None:
        # Use paths that definitely don't exist
        task = Task(
            title="t",
            files_to_remove=[
                str(tmp_path / "gone1.py"),
                str(tmp_path / "gone2.py"),
            ],
        )
        result = _check_files_to_remove(task, tmp_path)
        assert result.status is CheckStatus.PASS
        assert "2/2" in result.detail

    def test_some_still_exist_failed(self, tmp_path: Path) -> None:
        still_here = tmp_path / "still_here.py"
        still_here.write_text("oops")
        task = Task(
            title="t",
            files_to_remove=[
                str(still_here),
                str(tmp_path / "gone.py"),
            ],
        )
        result = _check_files_to_remove(task, tmp_path)
        assert result.status is CheckStatus.FAIL
        assert "1/2" in result.detail

    def test_none_removed_failed(self, tmp_path: Path) -> None:
        f = tmp_path / "exists.py"
        f.write_text("still here")
        task = Task(title="t", files_to_remove=[str(f)])
        result = _check_files_to_remove(task, tmp_path)
        assert result.status is CheckStatus.FAIL
        assert "0/1" in result.detail


# ===========================================================================
# _check_line_counts
# ===========================================================================


class TestCheckLineCounts:
    """Line-count tolerance checks including SKIPPED paths."""

    def test_zero_expected_lines_added_skipped(self) -> None:
        task = Task(
            title="t",
            files_to_create=["a.py"],
            expected_lines_added=0,
        )
        diff = FakeGitDiff()
        results = _check_line_counts(task, diff, "HEAD")
        added_r = next(r for r in results if r.name == "lines_added")
        assert added_r.status is CheckStatus.SKIP

    def test_zero_expected_lines_removed_skipped(self) -> None:
        task = Task(
            title="t",
            files_to_modify=["a.py"],
            expected_lines_removed=0,
        )
        diff = FakeGitDiff()
        results = _check_line_counts(task, diff, "HEAD")
        removed_r = next(r for r in results if r.name == "lines_removed")
        assert removed_r.status is CheckStatus.SKIP

    def test_no_add_files_skipped(self) -> None:
        # No files_to_create or files_to_modify -> no add_files
        task = Task(
            title="t",
            files_to_remove=["x.py"],
            expected_lines_added=50,
        )
        diff = FakeGitDiff()
        results = _check_line_counts(task, diff, "HEAD")
        added_r = next(r for r in results if r.name == "lines_added")
        assert added_r.status is CheckStatus.SKIP

    def test_within_tolerance_passed(self) -> None:
        task = Task(
            title="t",
            files_to_modify=["a.py"],
            expected_lines_added=100,
            expected_lines_removed=50,
        )
        diff = FakeGitDiff(stats={"a.py": (105, 48)})
        results = _check_line_counts(task, diff, "HEAD")
        added_r = next(r for r in results if r.name == "lines_added")
        removed_r = next(r for r in results if r.name == "lines_removed")
        assert added_r.status is CheckStatus.PASS
        assert removed_r.status is CheckStatus.PASS

    def test_outside_tolerance_failed(self) -> None:
        task = Task(
            title="t",
            files_to_modify=["a.py"],
            expected_lines_added=100,
            expected_lines_removed=50,
        )
        # 100 + 30% = 130 max; 200 is way over
        diff = FakeGitDiff(stats={"a.py": (200, 200)})
        results = _check_line_counts(task, diff, "HEAD")
        added_r = next(r for r in results if r.name == "lines_added")
        removed_r = next(r for r in results if r.name == "lines_removed")
        assert added_r.status is CheckStatus.FAIL
        assert removed_r.status is CheckStatus.FAIL


# ===========================================================================
# _validate_params
# ===========================================================================


class TestValidateParams:
    """Error paths for _validate_params."""

    def test_task_index_negative(self) -> None:
        promise = _promise_with_tasks(Task(title="t", task_id="aaa"))
        with pytest.raises(PromiseError, match="out of range"):
            _validate_params(-1, FakeGitDiff(), None, promise)

    def test_task_index_too_large(self) -> None:
        promise = _promise_with_tasks(Task(title="t", task_id="aaa"))
        with pytest.raises(PromiseError, match="out of range"):
            _validate_params(5, FakeGitDiff(), None, promise)

    def test_empty_promise_error_message(self) -> None:
        promise = Promise(metadata=Metadata())
        with pytest.raises(PromiseError, match="no tasks in promise"):
            _validate_params(0, FakeGitDiff(), None, promise)

    def test_valid_index_returns_diff_and_promise(self) -> None:
        fake = FakeGitDiff()
        promise = _promise_with_tasks(Task(title="t", task_id="aaa"))
        diff, p = _validate_params(0, fake, None, promise)
        assert diff is fake
        assert p is promise

    def test_loads_from_path_when_promise_none(self, tmp_path: Path) -> None:
        promise = _promise_with_tasks(Task(title="loaded", task_id="bbb"))
        pfile = tmp_path / "cp.toml"
        save_promise(promise, pfile)
        diff, p = _validate_params(0, FakeGitDiff(), pfile, None)
        assert p.tasks[0].title == "loaded"


# ===========================================================================
# check_task  (integration)
# ===========================================================================


class TestCheckTask:
    """Integration tests for check_task using FakeGitDiff."""

    def test_pre_commit_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Task verification FAIL if pre-commit hooks fail (SPEC R32)."""
        monkeypatch.setattr(
            "prothon.promise_verify.run_pre_commit", lambda _p, **_k: (1, "Failed")
        )

        task = Task(title="fail hooks", task_id="t_fail", files_to_modify=["a.py"])
        pfile = tmp_path / "docs" / "promise.toml"
        pfile.parent.mkdir()
        save_promise(_promise_with_tasks(task), pfile)

        diff = FakeGitDiff(names={"a.py"}, stats={"a.py": (10, 0)})
        report = check_task(0, diff=diff, path=pfile)

        assert report.passed is False
        check = next(c for c in report.checks if c.name == "pre-commit")
        assert check.status == CheckStatus.FAIL
        assert "hooks failed" in check.detail

    def test_all_checks_pass(self, tmp_path: Path) -> None:
        # Create the files on disk so files_to_create passes
        (tmp_path / "new.py").write_text("content")

        task = Task(
            title="do stuff",
            task_id="t1",
            files_to_create=["new.py"],
            files_to_modify=["src/app.py"],
            expected_lines_added=100,
            expected_lines_removed=0,
        )
        promise = _promise_with_tasks(task)
        pfile = tmp_path / "docs" / "change_promise.toml"
        pfile.parent.mkdir()
        save_promise(promise, pfile)

        diff = FakeGitDiff(
            names={"src/app.py", "new.py"},
            stats={"new.py": (60, 0), "src/app.py": (40, 0)},
        )
        report = check_task(0, diff=diff, path=pfile, promise=promise)
        assert report.passed is True
        assert report.task_id == "t1"

    def test_failed_check_report(self, tmp_path: Path) -> None:
        # files_to_create will fail because no file on disk
        task = Task(
            title="missing",
            task_id="t2",
            files_to_create=["ghost.py"],
            expected_lines_added=0,
        )
        promise = _promise_with_tasks(task)
        pfile = tmp_path / "docs" / "change_promise.toml"
        pfile.parent.mkdir()
        save_promise(promise, pfile)

        diff = FakeGitDiff()
        report = check_task(0, diff=diff, path=pfile, promise=promise)
        assert report.passed is False
        create_check = next(c for c in report.checks if c.name == "files_to_create")
        assert create_check.status is CheckStatus.FAIL

    def test_out_of_range_index_raises(self) -> None:
        promise = _promise_with_tasks(Task(title="t", task_id="x"))
        with pytest.raises(PromiseError, match="out of range"):
            check_task(99, diff=FakeGitDiff(), promise=promise)

    def test_format_report(self, tmp_path: Path) -> None:
        task = Task(title="fmt test", task_id="f1")
        promise = _promise_with_tasks(task)
        pfile = tmp_path / "docs" / "change_promise.toml"
        pfile.parent.mkdir()
        save_promise(promise, pfile)

        report = check_task(0, diff=FakeGitDiff(), path=pfile, promise=promise)
        formatted = report.format()
        assert "fmt test" in formatted
        assert "PASS" in formatted
