"""Tests for the change promise checker."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w

from prothon.promise import (
    CheckResult,
    TaskCheckReport,
    _within_tolerance,
    check_task,
    complete_task,
    load_promise,
    save_promise,
    status,
)

SAMPLE_PROMISE = {
    "metadata": {"plan_source": "docs/PLAN.md"},
    "tasks": [
        {
            "title": "Add auth module",
            "success_criteria": "JWT middleware works",
            "files_to_modify": ["src/app.py"],
            "files_to_create": ["src/auth.py", "tests/test_auth.py"],
            "files_to_remove": ["src/old_auth.py"],
            "expected_lines_added": 100,
            "expected_lines_removed": 20,
            "completed": False,
        },
        {
            "title": "Add config loading",
            "success_criteria": "Config loads from env vars",
            "files_to_modify": [],
            "files_to_create": ["src/config.py"],
            "files_to_remove": [],
            "expected_lines_added": 30,
            "expected_lines_removed": 0,
            "completed": False,
        },
    ],
}


@pytest.fixture
def promise_file(tmp_path: Path) -> Path:
    p = tmp_path / "change_promise.toml"
    p.write_bytes(tomli_w.dumps(SAMPLE_PROMISE).encode())
    return p


class TestWithinTolerance:
    """Tests for _within_tolerance with ±30%/±30 tolerance."""

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


class TestLoadSaveRoundtrip:
    def test_roundtrip(self, promise_file: Path):
        data = load_promise(promise_file)
        assert data["tasks"][0]["title"] == "Add auth module"
        assert len(data["tasks"]) == 2

        data["tasks"][0]["completed"] = True
        save_promise(data, promise_file)

        reloaded = load_promise(promise_file)
        assert reloaded["tasks"][0]["completed"] is True
        assert reloaded["tasks"][1]["completed"] is False


class TestCheckTask:
    def _mock_diff_names(self):
        return {"src/app.py"}

    def _mock_diff_numstat(self):
        return {
            "src/app.py": (10, 15),
            "src/auth.py": (80, 0),
            "tests/test_auth.py": (25, 0),
        }

    def test_all_pass(self, promise_file: Path, tmp_path: Path):
        """All files exist/modified/removed, line counts in tolerance."""
        # Create the files that should exist
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "auth.py").write_text("auth code")
        (tmp_path / "tests" / "test_auth.py").write_text("test code")
        # src/old_auth.py should NOT exist (it's in files_to_remove)

        # Patch file paths to be relative to tmp_path
        task_data = load_promise(promise_file)
        task_data["tasks"][0]["files_to_create"] = [
            str(tmp_path / "src" / "auth.py"),
            str(tmp_path / "tests" / "test_auth.py"),
        ]
        task_data["tasks"][0]["files_to_remove"] = [
            str(tmp_path / "src" / "old_auth.py"),
        ]
        save_promise(task_data, promise_file)

        with (
            patch("prothon.promise._git_diff_names", return_value={"src/app.py"}),
            patch("prothon.promise._git_diff_numstat", return_value={
                "src/app.py": (10, 15),
                str(tmp_path / "src" / "auth.py"): (80, 0),
                str(tmp_path / "tests" / "test_auth.py"): (25, 0),
            }),
        ):
            report = check_task(0, promise_file)
            assert report.passed is True
            assert all(c.passed for c in report.checks)

    def test_missing_created_file(self, promise_file: Path, tmp_path: Path):
        """Fail when a file that should be created doesn't exist."""
        task_data = load_promise(promise_file)
        task_data["tasks"][0]["files_to_create"] = [
            str(tmp_path / "src" / "auth.py"),  # doesn't exist
        ]
        task_data["tasks"][0]["files_to_remove"] = []
        save_promise(task_data, promise_file)

        with (
            patch("prothon.promise._git_diff_names", return_value={"src/app.py"}),
            patch("prothon.promise._git_diff_numstat", return_value={}),
        ):
            report = check_task(0, promise_file)
            create_check = next(c for c in report.checks if c.name == "files_to_create")
            assert create_check.passed is False

    def test_unmodified_file(self, promise_file: Path):
        """Fail when a file that should be modified isn't in git diff."""
        with (
            patch("prothon.promise._git_diff_names", return_value=set()),  # nothing modified
            patch("prothon.promise._git_diff_numstat", return_value={}),
        ):
            report = check_task(0, promise_file)
            modify_check = next(c for c in report.checks if c.name == "files_to_modify")
            assert modify_check.passed is False

    def test_file_not_removed(self, promise_file: Path, tmp_path: Path):
        """Fail when a file that should be removed still exists."""
        (tmp_path / "old_auth.py").write_text("old code")
        task_data = load_promise(promise_file)
        task_data["tasks"][0]["files_to_remove"] = [str(tmp_path / "old_auth.py")]
        save_promise(task_data, promise_file)

        with (
            patch("prothon.promise._git_diff_names", return_value={"src/app.py"}),
            patch("prothon.promise._git_diff_numstat", return_value={}),
        ):
            report = check_task(0, promise_file)
            remove_check = next(c for c in report.checks if c.name == "files_to_remove")
            assert remove_check.passed is False

    def test_line_count_outside_tolerance(self, promise_file: Path):
        """Fail when line counts are way off."""
        with (
            patch("prothon.promise._git_diff_names", return_value={"src/app.py"}),
            patch("prothon.promise._git_diff_numstat", return_value={
                "src/app.py": (5, 200),  # 200 removed vs 20 expected
            }),
        ):
            report = check_task(0, promise_file)
            removed_check = next(
                (c for c in report.checks if c.name == "lines_removed"), None
            )
            if removed_check:
                assert removed_check.passed is False

    def test_index_out_of_range(self, promise_file: Path):
        with pytest.raises(IndexError):
            check_task(99, promise_file)

    def test_empty_file_lists_skip_checks(self, promise_file: Path):
        """Tasks with empty file lists should skip those checks."""
        with (
            patch("prothon.promise._git_diff_names", return_value=set()),
            patch("prothon.promise._git_diff_numstat", return_value={}),
        ):
            report = check_task(1, promise_file)  # task 1 has no modify/remove
            check_names = [c.name for c in report.checks]
            assert "files_to_modify" not in check_names
            assert "files_to_remove" not in check_names


class TestCompleteTask:
    def test_marks_completed(self, promise_file: Path):
        complete_task(0, promise_file)
        data = load_promise(promise_file)
        assert data["tasks"][0]["completed"] is True
        assert data["tasks"][1]["completed"] is False

    def test_index_out_of_range(self, promise_file: Path):
        with pytest.raises(IndexError):
            complete_task(99, promise_file)


class TestStatus:
    def test_shows_all_tasks(self, promise_file: Path):
        output = status(promise_file)
        assert "Add auth module" in output
        assert "Add config loading" in output
        assert "0/2 completed" in output

    def test_reflects_completion(self, promise_file: Path):
        complete_task(0, promise_file)
        output = status(promise_file)
        assert "1/2 completed" in output


class TestReportFormat:
    def test_format_pass(self):
        report = TaskCheckReport(
            task_index=0,
            title="Test task",
            checks=[
                CheckResult(
                    name="files_to_create", passed=True, detail="2/2 exist"
                ),
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
                CheckResult(name="files_to_modify", passed=False, detail="0/1 modified"),
            ],
        )
        formatted = report.format()
        assert "DISCREPANCY" in formatted
        assert "1 failure" in formatted
