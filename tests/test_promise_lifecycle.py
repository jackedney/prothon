"""Tests for promise lifecycle: complete_task, record_attempt, status."""

from __future__ import annotations

from pathlib import Path

import pytest
from prothon.compliance import CheckStatus
from prothon.exceptions import MaxAttemptsExceeded, PromiseError
from prothon.models import Metadata, Promise, Task
from prothon.promise import (
    complete_task,
    load_promise,
    record_attempt,
    save_promise,
    status,
)
from prothon.promise_verify import check_task

from tests.conftest import FakeGitDiff


@pytest.fixture(autouse=True)
def mock_pre_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prothon.promise_verify.run_pre_commit", lambda _p, **_k: (0, "Passed")
    )


def test_complete_task_marks_completed(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Task A"), Task(title="Task B")],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    complete_task(0, diff=FakeGitDiff(), path=p)
    result = load_promise(p)
    assert result.tasks[0].completed is True
    assert result.tasks[1].completed is False


def test_complete_task_index_out_of_range(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Task A"), Task(title="Task B")],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    with pytest.raises(PromiseError):
        complete_task(99, diff=FakeGitDiff(), path=p)


def test_complete_task_preserves_persisted_attempts(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Test", attempts=3)],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    complete_task(0, diff=FakeGitDiff(), path=p)
    result = load_promise(p)
    assert result.tasks[0].completed is True
    assert result.tasks[0].attempts == 3


def test_complete_task_refuses_when_checks_fail(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Create file", files_to_create=["missing.py"])],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    with pytest.raises(PromiseError, match="promise checks failed"):
        complete_task(0, diff=FakeGitDiff(), path=p)


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


def test_record_attempt_preserves_comments(tmp_path: Path):
    p = tmp_path / "promise.toml"
    p.write_text(
        '[metadata]\nbase_commit = "abc"\n\n'
        "# This is a task comment\n"
        "[[tasks]]\n"
        'title = "Test"\n'
        'task_id = "deadbeef"\n'
        'goal = ""\n'
        'success_criteria = ""\n'
        "files_to_create = []\n"
        "files_to_modify = []\n"
        "files_to_remove = []\n"
        "expected_lines_added = 0\n"
        "expected_lines_removed = 0\n"
        "context_files = []\n"
        "doc_sections = []\n"
        "reference_skills = []\n"
        "dependencies = []\n"
        "completed = false\n"
        "attempts = 0\n"
        "max_attempts = 3\n",
        encoding="utf-8",
    )
    record_attempt(0, path=p)
    content = p.read_text(encoding="utf-8")
    assert "# This is a task comment" in content
    assert "attempts = 1" in content


def test_record_attempt_increments_counter(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Test", attempts=1)],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    record_attempt(0, path=p)
    assert load_promise(p).tasks[0].attempts == 2
    record_attempt(0, path=p)
    assert load_promise(p).tasks[0].attempts == 3


def test_record_attempt_index_out_of_range(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Test")],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    with pytest.raises(PromiseError, match="out of range"):
        record_attempt(99, path=p)


def test_record_attempt_parallel_no_lost_updates(tmp_path: Path):
    import concurrent.futures

    p_obj = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Concurrent", attempts=0, max_attempts=10)],
    )
    path = tmp_path / "promise.toml"
    save_promise(p_obj, path)
    n_threads = 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as pool:
        futures = [pool.submit(record_attempt, 0, path=path) for _ in range(n_threads)]
        for f in futures:
            f.result()
    assert load_promise(path).tasks[0].attempts == n_threads


def test_record_attempt_raises_max_attempts_exceeded(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Exhausted", attempts=3, max_attempts=3)],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    with pytest.raises(MaxAttemptsExceeded, match="maximum retry attempts"):
        record_attempt(0, path=p)
    assert load_promise(p).tasks[0].attempts == 3


def test_status_shows_all_tasks(tmp_path: Path):
    promise = Promise(
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
    p = tmp_path / "change_promise.toml"
    save_promise(promise, p)
    output = status(p)
    assert "Add auth module" in output
    assert "Add config loading" in output
    assert "0/2 completed" in output


def test_status_reflects_completion(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Task A"), Task(title="Task B")],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    complete_task(0, diff=FakeGitDiff(), path=p)
    assert "1/2 completed" in status(p)


def test_status_uses_checkmark_for_completed(tmp_path: Path):
    p = Promise(tasks=[Task(title="Done", completed=True)])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "\u2713" in status(path)


def test_status_uses_cross_for_incomplete(tmp_path: Path):
    p = Promise(tasks=[Task(title="Todo", completed=False)])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "\u2717" in status(path)


def test_status_shows_task_indices(tmp_path: Path):
    p = Promise(tasks=[Task(title="First"), Task(title="Second")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "0: First" in output
    assert "1: Second" in output


def test_status_exact_mark_format(tmp_path: Path):
    p = Promise(tasks=[Task(title="Done", completed=True), Task(title="Todo")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "[\u2713]" in output
    assert "[\u2717]" in output


def test_status_lines_joined_with_newline(tmp_path: Path):
    p = Promise(tasks=[Task(title="A"), Task(title="B")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = status(path)
    assert "XX" not in output
    lines = output.split("\n")
    assert len(lines) >= 3


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
        metadata=Metadata(), tasks=[Task(title="T", files_to_modify=["a.py", "b.py"])]
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
        tasks=[Task(title="T", files_to_remove=[str(tmp_path / "a.py"), "gone.py"])],
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


def test_check_task_skipped_files_to_create_check_name(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    report = check_task(0, diff=FakeGitDiff(), path=path)
    assert report.checks[0].name == "files_to_create"
    assert report.checks[0].status is CheckStatus.SKIP


def test_check_task_out_of_range_empty_tasks_message(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError, match="no tasks"):
        check_task(0, diff=FakeGitDiff(), path=path)


def test_check_task_out_of_range_shows_valid_range(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[Task(title="T1"), Task(title="T2")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError, match=r"Task index 5 out of range \(0-1\)"):
        check_task(5, diff=FakeGitDiff(), path=path)


def test_check_task_negative_index_rejected(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError, match=r"Task index -1 out of range \(0-0\)"):
        check_task(-1, diff=FakeGitDiff(), path=path)


def test_check_task_out_of_range_at_boundary(tmp_path: Path):
    p = Promise(metadata=Metadata(), tasks=[Task(title="T1"), Task(title="T2")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    with pytest.raises(PromiseError, match=r"Task index 2 out of range \(0-1\)"):
        check_task(2, diff=FakeGitDiff(), path=path)


def test_format_task_plan_basic():
    from prothon.promise import _format_task_plan

    task = Task(
        title="My Task",
        goal="My Goal",
        expected_lines_added=100,
        expected_lines_removed=20,
    )
    text = "\n".join(_format_task_plan(0, task))
    assert "Task 0: My Task" in text
    assert "Goal:   My Goal" in text
    assert "+100 / -20" in text
    assert "Deps:   none" in text


def test_format_task_plan_with_all_file_lists():
    from prothon.promise import _format_task_plan

    task = Task(
        title="T",
        files_to_create=["a.py"],
        files_to_modify=["b.py"],
        files_to_remove=["c.py"],
        context_files=["ctx.py"],
        reference_skills=["tech-x"],
        doc_sections=["SPEC.md#API"],
    )
    text = "\n".join(_format_task_plan(0, task))
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
    from prothon.promise import _format_task_plan

    text = "\n".join(_format_task_plan(2, Task(title="T", dependencies=["H0", "H1"])))
    assert "Deps:   H0, H1" in text
    assert "Deps:   none" not in text


def test_format_task_plan_no_goal_omits_line():
    from prothon.promise import _format_task_plan

    assert "Goal:" not in "\n".join(_format_task_plan(0, Task(title="T")))


def test_format_task_plan_empty_file_lists_omitted():
    from prothon.promise import _format_task_plan

    text = "\n".join(_format_task_plan(0, Task(title="T")))
    assert "Create:" not in text
    assert "Modify:" not in text
    assert "Remove:" not in text
    assert "Reads:" not in text
    assert "Skills:" not in text
    assert "Docs:" not in text


def test_format_task_plan_ends_with_empty_line():
    from prothon.promise import _format_task_plan

    assert _format_task_plan(0, Task(title="T"))[-1] == ""


def test_format_task_plan_index_in_title():
    from prothon.promise import _format_task_plan

    assert _format_task_plan(3, Task(title="T"))[0] == "Task 3: T"


def test_format_task_plan_comma_separator():
    from prothon.promise import _format_task_plan

    text = "\n".join(
        _format_task_plan(0, Task(title="T", files_to_create=["a.py", "b.py"]))
    )
    assert "a.py, b.py" in text


def test_format_task_plan_deps_none_exact_indent():
    from prothon.promise import _format_task_plan

    assert "  Deps:   none" in _format_task_plan(0, Task(title="T"))
