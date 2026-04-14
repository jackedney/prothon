"""Tests for the change promise checker — core check_task and verification primitives."""

from __future__ import annotations

from pathlib import Path

import pytest
from prothon.compliance import CheckStatus
from prothon.models import Metadata, Promise, Task
from prothon.promise import load_promise, save_promise
from prothon.promise_verify import (
    CheckResult,
    TaskCheckReport,
    _check_line_count,
    _check_line_counts,
    check_task,
)

from tests.conftest import FakeGitDiff, make_task


@pytest.fixture(autouse=True)
def mock_pre_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prothon.promise_verify.run_pre_commit", lambda _p, **_k: (0, "Passed")
    )


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


# --- check_task ---


def test_check_task_all_pass(promise_file: Path, tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "auth.py").write_text("auth code")
    (tmp_path / "tests" / "test_auth.py").write_text("test code")

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
    assert not any(c.status is CheckStatus.FAIL for c in report.checks)


def test_check_task_missing_created_file(promise_file: Path, tmp_path: Path):
    promise = load_promise(promise_file)
    promise.tasks[0].files_to_create = [
        str(tmp_path / "src" / "auth.py"),
    ]
    promise.tasks[0].files_to_remove = []
    save_promise(promise, promise_file)

    fake_diff = FakeGitDiff(names={"src/app.py"})
    report = check_task(0, diff=fake_diff, path=promise_file)
    create_check = next(c for c in report.checks if c.name == "files_to_create")
    assert create_check.status is CheckStatus.FAIL


def test_check_task_unmodified_file(promise_file: Path):
    fake_diff = FakeGitDiff(names=set())
    report = check_task(0, diff=fake_diff, path=promise_file)
    modify_check = next(c for c in report.checks if c.name == "files_to_modify")
    assert modify_check.status is CheckStatus.FAIL


def test_check_task_file_not_removed(promise_file: Path, tmp_path: Path):
    (tmp_path / "old_auth.py").write_text("old code")
    promise = load_promise(promise_file)
    promise.tasks[0].files_to_remove = [str(tmp_path / "old_auth.py")]
    save_promise(promise, promise_file)

    fake_diff = FakeGitDiff(names={"src/app.py"})
    report = check_task(0, diff=fake_diff, path=promise_file)
    remove_check = next(c for c in report.checks if c.name == "files_to_remove")
    assert remove_check.status is CheckStatus.FAIL


def test_check_task_line_count_outside_tolerance(promise_file: Path):
    fake_diff = FakeGitDiff(
        names={"src/app.py"},
        stats={"src/app.py": (5, 200)},
    )
    report = check_task(0, diff=fake_diff, path=promise_file)
    removed_check = next(c for c in report.checks if c.name == "lines_removed")
    assert removed_check.status is CheckStatus.FAIL


def test_check_task_empty_file_lists_are_skipped(promise_file: Path):
    fake_diff = FakeGitDiff()
    report = check_task(1, diff=fake_diff, path=promise_file)
    by_name = {c.name: c for c in report.checks}
    assert by_name["files_to_modify"].status is CheckStatus.SKIP
    assert by_name["files_to_remove"].status is CheckStatus.SKIP


# --- TaskCheckReport.format ---


def test_report_format_pass():
    report = TaskCheckReport(
        task_index=0,
        title="Test task",
        task_id="fake_id",
        checks=[
            CheckResult(
                name="files_to_create", status=CheckStatus.PASS, detail="2/2 exist"
            ),
        ],
    )
    formatted = report.format()
    assert "PASS" in formatted
    assert "DISCREPANCY" not in formatted


def test_report_format_discrepancy():
    report = TaskCheckReport(
        task_index=0,
        title="Test task",
        task_id="fake_id",
        checks=[
            CheckResult(
                name="files_to_create", status=CheckStatus.PASS, detail="2/2 exist"
            ),
            CheckResult(
                name="files_to_modify", status=CheckStatus.FAIL, detail="0/1 modified"
            ),
        ],
    )
    formatted = report.format()
    assert "DISCREPANCY" in formatted
    assert "1 failure" in formatted


def test_report_format_skip_does_not_cause_failure():
    report = TaskCheckReport(
        task_index=0,
        title="Test task",
        task_id="fake_id",
        checks=[
            CheckResult(
                name="files_to_create", status=CheckStatus.PASS, detail="1/1 exist"
            ),
            CheckResult(
                name="files_to_modify",
                status=CheckStatus.SKIP,
                detail="none declared",
            ),
        ],
    )
    formatted = report.format()
    assert "SKIP" in formatted
    assert "DISCREPANCY" not in formatted


# --- make_task factory ---


def test_make_task_defaults():
    task_dict = make_task()
    assert task_dict["title"] == "test task"
    assert task_dict["expected_lines_added"] == 50
    assert task_dict["completed"] is False
    assert task_dict["max_attempts"] == 3


def test_make_task_overrides():
    task_dict = make_task(
        title="custom", expected_lines_added=200, completed=True, max_attempts=5
    )
    assert task_dict["title"] == "custom"
    assert task_dict["expected_lines_added"] == 200
    assert task_dict["completed"] is True
    assert task_dict["max_attempts"] == 5


# --- _check_line_count ---


def test_check_line_count_pass_has_correct_fields():
    result = _check_line_count("lines_added", 100, 100)
    assert result.status is CheckStatus.PASS
    assert result.name == "lines_added"
    assert "expected ~100" in result.detail
    assert "actual 100" in result.detail
    assert "tolerance" not in result.detail


def test_check_line_count_fail_has_tolerance_detail():
    result = _check_line_count("lines_removed", 100, 200)
    assert result.status is CheckStatus.FAIL
    assert result.name == "lines_removed"
    assert "expected ~100" in result.detail
    assert "actual 200" in result.detail
    assert "tolerance" in result.detail


def test_check_line_count_fail_detail_has_em_dash():
    result = _check_line_count("lines_added", 100, 200)
    assert " \u2014 outside " in result.detail


def test_check_line_count_fail_detail_no_xx():
    result = _check_line_count("lines_added", 100, 200)
    assert "XX" not in result.detail


# --- _check_line_counts ---


def test_check_line_counts_skips_when_no_files():
    task = Task(title="T")
    results = _check_line_counts(task, FakeGitDiff(), "HEAD")
    assert len(results) == 2
    assert results[0].name == "lines_added"
    assert results[0].status is CheckStatus.SKIP
    assert results[0].detail == "none expected"
    assert results[1].name == "lines_removed"
    assert results[1].status is CheckStatus.SKIP
    assert results[1].detail == "none expected"


def test_check_line_counts_skips_when_zero_expected():
    task = Task(
        title="T",
        files_to_modify=["a.py"],
        expected_lines_added=0,
        expected_lines_removed=0,
    )
    results = _check_line_counts(task, FakeGitDiff(stats={"a.py": (10, 5)}), "HEAD")
    assert results[0].status is CheckStatus.SKIP
    assert results[1].status is CheckStatus.SKIP


def test_check_line_counts_add_files_includes_create_and_modify():
    task = Task(
        title="T",
        files_to_create=["new.py"],
        files_to_modify=["mod.py"],
        expected_lines_added=100,
    )
    diff = FakeGitDiff(stats={"new.py": (60, 0), "mod.py": (40, 10)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    assert added.status is CheckStatus.PASS


def test_check_line_counts_remove_files_includes_modify_and_remove():
    task = Task(
        title="T",
        files_to_modify=["mod.py"],
        files_to_remove=["old.py"],
        expected_lines_removed=50,
    )
    diff = FakeGitDiff(stats={"mod.py": (10, 30), "old.py": (0, 20)})
    results = _check_line_counts(task, diff, "HEAD")
    removed = next(r for r in results if r.name == "lines_removed")
    assert removed.status is CheckStatus.PASS


def test_check_line_counts_reads_correct_tuple_index():
    task = Task(
        title="T",
        files_to_create=["f.py"],
        files_to_remove=["g.py"],
        expected_lines_added=100,
        expected_lines_removed=50,
    )
    diff = FakeGitDiff(stats={"f.py": (100, 999), "g.py": (999, 50)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    removed = next(r for r in results if r.name == "lines_removed")
    assert added.status is CheckStatus.PASS
    assert removed.status is CheckStatus.PASS


def test_check_line_counts_missing_file_defaults_to_zero():
    task = Task(
        title="T",
        files_to_create=["missing.py"],
        expected_lines_added=0,
        expected_lines_removed=0,
    )
    results = _check_line_counts(task, FakeGitDiff(stats={}), "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    assert added.status is CheckStatus.SKIP


def test_check_line_counts_only_create_files_no_modify():
    task = Task(
        title="T",
        files_to_create=["new.py"],
        expected_lines_added=50,
    )
    diff = FakeGitDiff(stats={"new.py": (50, 0)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    removed = next(r for r in results if r.name == "lines_removed")
    assert added.status is CheckStatus.PASS
    assert removed.status is CheckStatus.SKIP


def test_check_line_counts_only_remove_files_no_modify():
    task = Task(
        title="T",
        files_to_remove=["old.py"],
        expected_lines_removed=50,
    )
    diff = FakeGitDiff(stats={"old.py": (0, 50)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    removed = next(r for r in results if r.name == "lines_removed")
    assert added.status is CheckStatus.SKIP
    assert removed.status is CheckStatus.PASS


# --- Mutant-killing tests ---


def test_check_line_counts_expected_one_is_not_skipped():
    task = Task(
        title="T",
        files_to_create=["f.py"],
        expected_lines_added=1,
    )
    diff = FakeGitDiff(stats={"f.py": (1, 0)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    assert added.status is not CheckStatus.SKIP


def test_check_line_counts_expected_one_removed_is_not_skipped():
    task = Task(
        title="T",
        files_to_remove=["f.py"],
        expected_lines_removed=1,
    )
    diff = FakeGitDiff(stats={"f.py": (0, 1)})
    results = _check_line_counts(task, diff, "HEAD")
    removed = next(r for r in results if r.name == "lines_removed")
    assert removed.status is not CheckStatus.SKIP


def test_check_line_counts_missing_file_adds_zero_not_one():
    task = Task(
        title="T",
        files_to_create=["missing.py"],
        expected_lines_added=1,
    )
    diff = FakeGitDiff(stats={})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    assert "actual 0" in added.detail


def test_check_line_counts_missing_file_removed_zero():
    task = Task(
        title="T",
        files_to_remove=["missing.py"],
        expected_lines_removed=1,
    )
    diff = FakeGitDiff(stats={})
    results = _check_line_counts(task, diff, "HEAD")
    removed = next(r for r in results if r.name == "lines_removed")
    assert "actual 0" in removed.detail


# --- check_task detail assertions ---


def test_check_task_report_has_correct_title_and_index(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[Task(title="My Task")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    assert report.title == "My Task"
    assert report.task_index == 0
    import re

    assert isinstance(report.task_id, str)
    assert re.fullmatch(r"[0-9a-f]{8}", report.task_id)


def test_check_task_default_diff_is_subprocess(tmp_path: Path):
    from unittest.mock import MagicMock
    from unittest.mock import patch as mock_patch

    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)

    mock_cls = MagicMock()
    mock_instance = mock_cls.return_value
    mock_instance.diff_names.return_value = set()
    mock_instance.diff_numstat.return_value = {}
    with mock_patch("prothon.promise_verify.SubprocessGitDiff", mock_cls):
        check_task(0, path=path)
    mock_cls.assert_called_once()


def test_check_task_scopes_diff_to_task_files(tmp_path: Path):
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        new_file = Path("src/new.py")
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.touch()

        promise = Promise(
            metadata=Metadata(base_commit="abc1234"),
            tasks=[
                Task(
                    title="Task 1",
                    files_to_modify=["src/app.py"],
                    files_to_create=["src/new.py"],
                    files_to_remove=["src/old.py"],
                    expected_lines_added=10,
                    expected_lines_removed=5,
                ),
            ],
        )
        promise_path = Path("promise.toml")
        save_promise(promise, promise_path)

        fake_diff = FakeGitDiff(
            names={"src/app.py"},
            stats={
                "src/app.py": (5, 5),
                "src/new.py": (5, 0),
                "src/old.py": (0, 0),
                "unrelated.py": (100, 100),
            },
        )

        report = check_task(0, diff=fake_diff, path=promise_path)

        assert report.passed is True
        assert set(fake_diff.last_diff_names_paths) == {"src/app.py"}
        assert list(fake_diff.last_diff_numstat_paths) == [
            "src/app.py",
            "src/new.py",
            "src/old.py",
        ]

        added_check = next(c for c in report.checks if c.name == "lines_added")
        assert "actual 10" in added_check.detail
        removed_check = next(c for c in report.checks if c.name == "lines_removed")
        assert "actual 5" in removed_check.detail
    finally:
        os.chdir(old_cwd)
