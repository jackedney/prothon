"""Tests for the change promise checker."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from prothon.exceptions import PromiseError
from prothon.git import DiffStat
from prothon.promise import (
    CheckResult,
    CheckStatus,
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


# --- _within_tolerance ---


def test_within_tolerance_exact_match():
    assert _within_tolerance(100, 100) is True


def test_within_tolerance_at_thirty_percent_upper():
    # 100 + 30% = 130
    assert _within_tolerance(100, 130) is True


def test_within_tolerance_over_thirty_percent_upper():
    assert _within_tolerance(100, 131) is False


def test_within_tolerance_at_thirty_percent_lower():
    # 100 - 30% = 70
    assert _within_tolerance(100, 70) is True


def test_within_tolerance_under_thirty_percent_lower():
    assert _within_tolerance(100, 69) is False


def test_within_tolerance_absolute_floor_when_small_expected():
    # 10 expected, 30% = 3, but absolute minimum is 30
    # So tolerance is 30: range is -20 to 40
    assert _within_tolerance(10, 40) is True
    assert _within_tolerance(10, 41) is False


def test_within_tolerance_zero_expected_uses_absolute():
    # 0 expected, 30% = 0, absolute = 30
    assert _within_tolerance(0, 30) is True
    assert _within_tolerance(0, 31) is False


@given(expected=st.integers(min_value=0, max_value=10_000))
def test_within_tolerance_exact_match_always_passes(expected: int):
    """Hypothesis: exact match always passes regardless of expected value."""
    assert _within_tolerance(expected, expected) is True


@given(
    expected=st.integers(min_value=0, max_value=10_000),
    delta=st.integers(min_value=0, max_value=100_000),
)
def test_within_tolerance_is_symmetric(expected: int, delta: int):
    """Hypothesis: tolerance is symmetric -- +delta and -delta give same result."""
    above = _within_tolerance(expected, expected + delta)
    below = _within_tolerance(expected, expected - delta)
    assert above == below


# --- load_promise errors ---


def test_load_promise_missing_file_raises_promise_error(tmp_path: Path):
    with pytest.raises(PromiseError, match="promise file not found"):
        load_promise(tmp_path / "nonexistent.toml")


def test_load_promise_malformed_toml_raises_promise_error(tmp_path: Path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[invalid toml\n")
    with pytest.raises(PromiseError, match="malformed TOML"):
        load_promise(bad)


# --- load/save roundtrip ---


def test_load_save_roundtrip(promise_file: Path):
    promise = load_promise(promise_file)
    assert promise.tasks[0].title == "Add auth module"
    assert len(promise.tasks) == 2
    assert promise.tasks[0].max_attempts == 3

    promise.tasks[0].completed = True
    promise.tasks[0].max_attempts = 5
    save_promise(promise, promise_file)

    reloaded = load_promise(promise_file)
    assert reloaded.tasks[0].completed is True
    assert reloaded.tasks[0].max_attempts == 5
    assert reloaded.tasks[1].completed is False


def test_load_save_roundtrip_preserves_metadata(promise_file: Path):
    promise = load_promise(promise_file)
    assert promise.metadata.base_commit == "abc1234"

    save_promise(promise, promise_file)
    reloaded = load_promise(promise_file)
    assert reloaded.metadata.base_commit == "abc1234"


# --- check_task ---


def test_check_task_all_pass(promise_file: Path, tmp_path: Path):
    """All files exist/modified/removed, line counts in tolerance."""
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
    assert not any(c.status is CheckStatus.FAILED for c in report.checks)


def test_check_task_missing_created_file(promise_file: Path, tmp_path: Path):
    """Fail when a file that should be created doesn't exist."""
    promise = load_promise(promise_file)
    promise.tasks[0].files_to_create = [
        str(tmp_path / "src" / "auth.py"),
    ]
    promise.tasks[0].files_to_remove = []
    save_promise(promise, promise_file)

    fake_diff = FakeGitDiff(names={"src/app.py"})
    report = check_task(0, diff=fake_diff, path=promise_file)
    create_check = next(c for c in report.checks if c.name == "files_to_create")
    assert create_check.status is CheckStatus.FAILED


def test_check_task_unmodified_file(promise_file: Path):
    """Fail when a file that should be modified isn't in git diff."""
    fake_diff = FakeGitDiff(names=set())
    report = check_task(0, diff=fake_diff, path=promise_file)
    modify_check = next(c for c in report.checks if c.name == "files_to_modify")
    assert modify_check.status is CheckStatus.FAILED


def test_check_task_file_not_removed(promise_file: Path, tmp_path: Path):
    """Fail when a file that should be removed still exists."""
    (tmp_path / "old_auth.py").write_text("old code")
    promise = load_promise(promise_file)
    promise.tasks[0].files_to_remove = [str(tmp_path / "old_auth.py")]
    save_promise(promise, promise_file)

    fake_diff = FakeGitDiff(names={"src/app.py"})
    report = check_task(0, diff=fake_diff, path=promise_file)
    remove_check = next(c for c in report.checks if c.name == "files_to_remove")
    assert remove_check.status is CheckStatus.FAILED


def test_check_task_line_count_outside_tolerance(promise_file: Path):
    """Fail when line counts are way off."""
    fake_diff = FakeGitDiff(
        names={"src/app.py"},
        stats={"src/app.py": (5, 200)},
    )
    report = check_task(0, diff=fake_diff, path=promise_file)
    removed_check = next(c for c in report.checks if c.name == "lines_removed")
    assert removed_check.status is CheckStatus.FAILED


def test_check_task_raises_when_index_out_of_range(promise_file: Path):
    fake_diff = FakeGitDiff()
    with pytest.raises(PromiseError):
        check_task(99, diff=fake_diff, path=promise_file)


def test_check_task_empty_file_lists_are_skipped(promise_file: Path):
    """Tasks with empty file lists get SKIP status."""
    fake_diff = FakeGitDiff()
    report = check_task(1, diff=fake_diff, path=promise_file)
    by_name = {c.name: c for c in report.checks}
    assert by_name["files_to_modify"].status is CheckStatus.SKIPPED
    assert by_name["files_to_remove"].status is CheckStatus.SKIPPED


def test_check_task_passes_base_commit_to_diff_provider(tmp_path: Path):
    """check_task uses base_commit from promise metadata."""
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

    captured_commits: list[str] = []

    class CapturingFakeDiff:
        def diff_names(self, base_commit: str) -> set[str]:
            captured_commits.append(base_commit)
            return {"src/app.py"}

        def diff_numstat(self, base_commit: str) -> DiffStat:
            captured_commits.append(base_commit)
            return {"src/app.py": (50, 5)}

    check_task(0, diff=CapturingFakeDiff(), path=promise_path)
    assert captured_commits
    assert all(c == "abc1234" for c in captured_commits)


# --- complete_task ---


def test_complete_task_marks_completed(promise_file: Path):
    complete_task(0, path=promise_file)
    promise = load_promise(promise_file)
    assert promise.tasks[0].completed is True
    assert promise.tasks[1].completed is False


def test_complete_task_index_out_of_range(promise_file: Path):
    with pytest.raises(PromiseError):
        complete_task(99, path=promise_file)


def test_complete_task_records_attempts(tmp_path: Path):
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


def test_complete_task_defaults_to_one_attempt(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Test")],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)

    complete_task(0, path=p)

    result = load_promise(p)
    assert result.tasks[0].attempts == 1


# --- status ---


def test_status_shows_all_tasks(promise_file: Path):
    output = status(promise_file)
    assert "Add auth module" in output
    assert "Add config loading" in output
    assert "0/2 completed" in output


def test_status_reflects_completion(promise_file: Path):
    complete_task(0, path=promise_file)
    output = status(promise_file)
    assert "1/2 completed" in output


# --- TaskCheckReport.format ---


def test_report_format_pass():
    report = TaskCheckReport(
        task_index=0,
        title="Test task",
        checks=[
            CheckResult(
                name="files_to_create", status=CheckStatus.PASSED, detail="2/2 exist"
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
        checks=[
            CheckResult(
                name="files_to_create", status=CheckStatus.PASSED, detail="2/2 exist"
            ),
            CheckResult(
                name="files_to_modify", status=CheckStatus.FAILED, detail="0/1 modified"
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
        checks=[
            CheckResult(
                name="files_to_create", status=CheckStatus.PASSED, detail="1/1 exist"
            ),
            CheckResult(
                name="files_to_modify",
                status=CheckStatus.SKIPPED,
                detail="none declared",
            ),
        ],
    )
    formatted = report.format()
    assert "SKIP" in formatted
    assert "DISCREPANCY" not in formatted


# --- plan ---


def test_plan_formats_single_task(tmp_path: Path):
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


def test_plan_formats_dependencies(tmp_path: Path):
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


# --- cleanup ---


def test_cleanup_removes_promise_file(tmp_path: Path):
    p = tmp_path / "promise.toml"
    save_promise(Promise(), p)
    assert p.exists()

    cleanup(p)
    assert not p.exists()


def test_cleanup_raises_if_file_missing(tmp_path: Path):
    p = tmp_path / "promise.toml"
    with pytest.raises(FileNotFoundError):
        cleanup(p)


# --- make_task factory ---


def test_make_task_defaults():
    task_dict = make_task()
    assert task_dict["title"] == "test task"
    assert task_dict["expected_lines_added"] == 50
    assert task_dict["completed"] is False


def test_make_task_overrides():
    task_dict = make_task(title="custom", expected_lines_added=200, completed=True)
    assert task_dict["title"] == "custom"
    assert task_dict["expected_lines_added"] == 200
    assert task_dict["completed"] is True
