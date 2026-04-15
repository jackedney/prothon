"""Tests for the change promise checker."""

from __future__ import annotations

from pathlib import Path

import pytest
from prothon.compliance import CheckStatus
from prothon.exceptions import PromiseError
from prothon.models import Metadata, Promise, Task
from prothon.promise import (
    _format_task_plan,
    complete_task,
    load_promise,
    plan,
    save_promise,
    status,
)
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
    """Mock pre-commit execution for all tests to avoid environment dependencies."""
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


def test_check_task_files_to_create_detail(tmp_path: Path):
    (tmp_path / "a.py").write_text("x")
    p = Promise(
        metadata=Metadata(),
        tasks=[
            Task(
                title="T",
                files_to_create=[str(tmp_path / "a.py"), str(tmp_path / "b.py")],
            )
        ],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    create_check = next(c for c in report.checks if c.name == "files_to_create")
    assert "1/2" in create_check.detail
    assert create_check.status is CheckStatus.FAIL


def test_check_task_files_to_create_all_exist(tmp_path: Path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    p = Promise(
        metadata=Metadata(),
        tasks=[
            Task(
                title="T",
                files_to_create=[str(tmp_path / "a.py"), str(tmp_path / "b.py")],
            )
        ],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    create_check = next(c for c in report.checks if c.name == "files_to_create")
    assert "2/2" in create_check.detail
    assert create_check.status is CheckStatus.PASS


def test_check_task_files_to_modify_detail(tmp_path: Path):
    p = Promise(
        metadata=Metadata(),
        tasks=[Task(title="T", files_to_modify=["a.py", "b.py"])],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(names={"a.py"}), path=path)
    modify_check = next(c for c in report.checks if c.name == "files_to_modify")
    assert "1/2" in modify_check.detail
    assert modify_check.status is CheckStatus.FAIL


def test_check_task_files_to_remove_detail(tmp_path: Path):
    (tmp_path / "a.py").write_text("x")
    p = Promise(
        metadata=Metadata(),
        tasks=[
            Task(
                title="T",
                files_to_remove=[str(tmp_path / "a.py"), "gone.py"],
            )
        ],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    remove_check = next(c for c in report.checks if c.name == "files_to_remove")
    assert "1/2" in remove_check.detail
    assert remove_check.status is CheckStatus.FAIL


def test_check_task_skipped_detail_text(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    for c in report.checks:
        if c.status is CheckStatus.SKIP:
            assert c.detail in ("none declared", "none expected", "no files to check")


# --- complete_task edge cases ---


def test_complete_task_out_of_range_empty_message(tmp_path: Path):
    p = Promise(tasks=[])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError, match="no tasks"):
        complete_task(0, diff=FakeGitDiff(), path=path)


def test_complete_task_out_of_range_shows_range(tmp_path: Path):
    p = Promise(tasks=[Task(title="T1"), Task(title="T2")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError, match="0-1"):
        complete_task(5, diff=FakeGitDiff(), path=path)


def test_complete_task_negative_index_rejected(tmp_path: Path):
    p = Promise(tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError):
        complete_task(-1, diff=FakeGitDiff(), path=path)


def test_complete_task_parallel_no_lost_updates(tmp_path: Path):
    """Concurrent completions must not overwrite each other (GH-17)."""
    import concurrent.futures

    p = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="T0"), Task(title="T1"), Task(title="T2")],
    )
    path = tmp_path / "promise.toml"
    save_promise(p, path)
    fake = FakeGitDiff()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(complete_task, i, diff=fake, path=path) for i in range(3)
        ]
        for f in futures:
            f.result()

    result = load_promise(path)
    assert all(t.completed for t in result.tasks), (
        f"Expected all tasks completed, got: {[t.completed for t in result.tasks]}"
    )


# --- status detail ---


def test_status_uses_checkmark_for_completed(tmp_path: Path):
    p = Promise(tasks=[Task(title="Done", completed=True)])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "\u2713" in output


def test_status_uses_cross_for_incomplete(tmp_path: Path):
    p = Promise(tasks=[Task(title="Todo", completed=False)])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "\u2717" in output


def test_status_shows_task_indices(tmp_path: Path):
    p = Promise(tasks=[Task(title="First"), Task(title="Second")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "0: First" in output
    assert "1: Second" in output


# --- _format_task_plan ---


def test_format_task_plan_basic():
    task = Task(
        title="My Task",
        goal="My Goal",
        expected_lines_added=100,
        expected_lines_removed=20,
    )
    lines = _format_task_plan(0, task)
    text = "\n".join(lines)
    assert "Task 0: My Task" in text
    assert "Goal:   My Goal" in text
    assert "+100 / -20" in text
    assert "Deps:   none" in text


def test_format_task_plan_with_all_file_lists():
    task = Task(
        title="T",
        files_to_create=["a.py"],
        files_to_modify=["b.py"],
        files_to_remove=["c.py"],
        context_files=["ctx.py"],
        reference_skills=["tech-x"],
        doc_sections=["SPEC.md#API"],
    )
    lines = _format_task_plan(0, task)
    text = "\n".join(lines)
    assert "Create:" in text
    assert "a.py" in text
    assert "Modify:" in text
    assert "b.py" in text
    assert "Remove:" in text
    assert "c.py" in text
    assert "Reads:" in text
    assert "ctx.py" in text
    assert "Skills:" in text
    assert "tech-x" in text
    assert "Docs:" in text
    assert "SPEC.md#API" in text


def test_format_task_plan_with_deps():
    task = Task(title="T", dependencies=["H0", "H1"])
    lines = _format_task_plan(2, task)
    text = "\n".join(lines)
    assert "Deps:   H0, H1" in text
    assert "Deps:   none" not in text


def test_format_task_plan_no_goal_omits_line():
    task = Task(title="T")
    lines = _format_task_plan(0, task)
    text = "\n".join(lines)
    assert "Goal:" not in text


def test_format_task_plan_empty_file_lists_omitted():
    task = Task(title="T")
    lines = _format_task_plan(0, task)
    text = "\n".join(lines)
    assert "Create:" not in text
    assert "Modify:" not in text
    assert "Remove:" not in text
    assert "Reads:" not in text
    assert "Skills:" not in text
    assert "Docs:" not in text


def test_format_task_plan_ends_with_empty_line():
    task = Task(title="T")
    lines = _format_task_plan(0, task)
    assert lines[-1] == ""


def test_format_task_plan_index_in_title():
    task = Task(title="T")
    lines3 = _format_task_plan(3, task)
    assert lines3[0] == "Task 3: T"


# --- plan edge cases ---


def test_plan_singular_task_word(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "1 task " in output or "1 task\n" in output or output.endswith("1 task")
    assert "1 tasks" not in output


def test_plan_plural_tasks_word(tmp_path: Path):
    p = Promise(
        metadata=Metadata(base_commit="abc"),
        tasks=[Task(title="T1"), Task(title="T2")],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "2 tasks" in output


def test_plan_unknown_base_when_empty(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit=""), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "unknown" in output


def test_plan_no_deps_shows_none(tmp_path: Path):
    p = Promise(
        metadata=Metadata(base_commit="abc"),
        tasks=[Task(title="No deps task")],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "Deps:   none" in output


# --- Tests targeting specific surviving mutants ---


def test_check_line_counts_expected_one_is_not_skipped():
    """expected_lines_added=1 should NOT be skipped (kills <= 0 -> <= 1)."""
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
    """expected_lines_removed=1 should NOT be skipped (kills <= 0 -> <= 1)."""
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
    """Default for missing file is (0,0) not (1,0) or (0,1)
    -- kills default tuple mutations.
    """
    task = Task(
        title="T",
        files_to_create=["missing.py"],
        expected_lines_added=1,
    )
    # missing.py is NOT in stats, so default (0,0) should be used
    # with expected=1 and actual=0, within tolerance (abs tolerance 30) -> PASS
    diff = FakeGitDiff(stats={})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    assert "actual 0" in added.detail


def test_check_line_counts_missing_file_removed_zero():
    """Default for missing file removed count is 0."""
    task = Task(
        title="T",
        files_to_remove=["missing.py"],
        expected_lines_removed=1,
    )
    diff = FakeGitDiff(stats={})
    results = _check_line_counts(task, diff, "HEAD")
    removed = next(r for r in results if r.name == "lines_removed")
    assert "actual 0" in removed.detail


def test_check_task_skipped_files_to_create_check_name(tmp_path: Path):
    """When files_to_create is empty, the SKIPPED check is named
    exactly 'files_to_create'.
    """
    p = Promise(metadata=Metadata(), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    create_check = report.checks[0]
    assert create_check.name == "files_to_create"
    assert create_check.status is CheckStatus.SKIP


def test_status_exact_mark_format(tmp_path: Path):
    """Status output uses exact checkmark and cross brackets."""
    p = Promise(tasks=[Task(title="Done", completed=True), Task(title="Todo")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "[\u2713]" in output
    assert "[\u2717]" in output


def test_status_lines_joined_with_newline(tmp_path: Path):
    """Status output uses plain newline joiner, not a mutated one."""
    p = Promise(tasks=[Task(title="A"), Task(title="B")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "XX" not in output
    lines = output.split("\n")
    assert len(lines) >= 3


def test_plan_lines_joined_with_newline(tmp_path: Path):
    """Plan output uses plain newline joiner."""
    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "XX" not in output


def test_plan_has_blank_line_after_header(tmp_path: Path):
    """Second line of plan output is blank (empty string)."""
    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    lines = output.split("\n")
    assert lines[1] == ""


def test_plan_exact_unknown_string(tmp_path: Path):
    """Plan uses exactly 'unknown' for missing base_commit."""
    p = Promise(metadata=Metadata(base_commit=""), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "(base: unknown)" in output


def test_format_task_plan_comma_separator():
    """Multiple items are joined with ', ' not a mutated separator."""
    task = Task(title="T", files_to_create=["a.py", "b.py"])
    lines = _format_task_plan(0, task)
    text = "\n".join(lines)
    assert "a.py, b.py" in text


def test_format_task_plan_deps_none_exact_indent():
    """Deps none line has exact format with correct indentation."""
    task = Task(title="T")
    lines = _format_task_plan(0, task)
    assert "  Deps:   none" in lines


def test_check_line_count_fail_detail_has_em_dash():
    """Failed line count detail includes the em-dash separator."""
    result = _check_line_count("lines_added", 100, 200)
    assert " \u2014 outside " in result.detail


def test_save_promise_created_at_key_name(tmp_path: Path):
    """created_at is serialized with exact key name 'created_at'."""
    p = Promise(metadata=Metadata(base_commit="abc", created_at="2025-01-01"))
    path = tmp_path / "p.toml"
    save_promise(p, path)
    content = path.read_text()
    assert "created_at" in content
    reloaded = load_promise(path)
    assert reloaded.metadata.created_at == "2025-01-01"


def test_check_line_count_fail_detail_no_xx():
    """Failed tolerance detail must not have 'XX' padding (kills string mutation)."""
    result = _check_line_count("lines_added", 100, 200)
    assert "XX" not in result.detail


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
