"""Tests for the change promise checker."""

from __future__ import annotations

from pathlib import Path

import pytest
from prothon.compliance import CheckStatus
from prothon.exceptions import MaxAttemptsExceeded, PromiseError
from prothon.git import DiffStat
from prothon.models import Metadata, Promise, Task
from prothon.promise import (
    _format_task_plan,
    _metadata_from_dict,
    _task_from_dict,
    _task_to_dict,
    cleanup,
    complete_task,
    load_promise,
    plan,
    record_attempt,
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


# _within_tolerance tests are in test_promise_verify.py (single source of truth)

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
    assert not any(c.status is CheckStatus.FAIL for c in report.checks)


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
    assert create_check.status is CheckStatus.FAIL


def test_check_task_unmodified_file(promise_file: Path):
    """Fail when a file that should be modified isn't in git diff."""
    fake_diff = FakeGitDiff(names=set())
    report = check_task(0, diff=fake_diff, path=promise_file)
    modify_check = next(c for c in report.checks if c.name == "files_to_modify")
    assert modify_check.status is CheckStatus.FAIL


def test_check_task_file_not_removed(promise_file: Path, tmp_path: Path):
    """Fail when a file that should be removed still exists."""
    (tmp_path / "old_auth.py").write_text("old code")
    promise = load_promise(promise_file)
    promise.tasks[0].files_to_remove = [str(tmp_path / "old_auth.py")]
    save_promise(promise, promise_file)

    fake_diff = FakeGitDiff(names={"src/app.py"})
    report = check_task(0, diff=fake_diff, path=promise_file)
    remove_check = next(c for c in report.checks if c.name == "files_to_remove")
    assert remove_check.status is CheckStatus.FAIL


def test_check_task_line_count_outside_tolerance(promise_file: Path):
    """Fail when line counts are way off."""
    fake_diff = FakeGitDiff(
        names={"src/app.py"},
        stats={"src/app.py": (5, 200)},
    )
    report = check_task(0, diff=fake_diff, path=promise_file)
    removed_check = next(c for c in report.checks if c.name == "lines_removed")
    assert removed_check.status is CheckStatus.FAIL


def test_check_task_empty_file_lists_are_skipped(promise_file: Path):
    """Tasks with empty file lists get SKIP status."""
    fake_diff = FakeGitDiff()
    report = check_task(1, diff=fake_diff, path=promise_file)
    by_name = {c.name: c for c in report.checks}
    assert by_name["files_to_modify"].status is CheckStatus.SKIP
    assert by_name["files_to_remove"].status is CheckStatus.SKIP


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
        def diff_names(self, base_commit: str, *paths: str) -> set[str]:
            captured_commits.append(base_commit)
            return {"src/app.py"}

        def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat:
            captured_commits.append(base_commit)
            return {"src/app.py": (50, 5)}

    check_task(0, diff=CapturingFakeDiff(), path=promise_path)
    assert captured_commits
    assert all(c == "abc1234" for c in captured_commits)


# --- complete_task ---


def test_complete_task_marks_completed(tmp_path: Path):
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Task A"), Task(title="Task B")],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    fake = FakeGitDiff()

    complete_task(0, diff=fake, path=p)
    result = load_promise(p)
    assert result.tasks[0].completed is True
    assert result.tasks[1].completed is False


def test_complete_task_index_out_of_range(promise_file: Path):
    with pytest.raises(PromiseError):
        complete_task(99, diff=FakeGitDiff(), path=promise_file)


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


def test_task_from_dict_coerces_string_attempts():
    """Malformed attempts (e.g. quoted string) should raise PromiseError."""
    with pytest.raises(PromiseError, match="must be an integer"):
        _task_from_dict({"title": "Bad", "attempts": "zero"})


def test_record_attempt_preserves_comments(tmp_path: Path):
    """record_attempt must not destroy TOML comments (DESIGN.md requirement)."""
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

    result = load_promise(p)
    assert result.tasks[0].attempts == 2

    record_attempt(0, path=p)
    result = load_promise(p)
    assert result.tasks[0].attempts == 3


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
    """Concurrent record_attempt calls must not lose increments."""
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

    result = load_promise(path)
    assert result.tasks[0].attempts == n_threads


def test_record_attempt_raises_max_attempts_exceeded(tmp_path: Path):
    """record_attempt refuses to increment when attempts >= max_attempts."""
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Exhausted", attempts=3, max_attempts=3)],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)

    with pytest.raises(MaxAttemptsExceeded, match="maximum retry attempts"):
        record_attempt(0, path=p)

    # Verify counter was NOT incremented
    result = load_promise(p)
    assert result.tasks[0].attempts == 3


def test_complete_task_refuses_when_checks_fail(tmp_path: Path):
    """complete_task raises PromiseError when promise checks fail (SPEC R34)."""
    promise = Promise(
        metadata=Metadata(base_commit="abc1234"),
        tasks=[Task(title="Create file", files_to_create=["missing.py"])],
    )
    p = tmp_path / "promise.toml"
    save_promise(promise, p)
    fake = FakeGitDiff()

    with pytest.raises(PromiseError, match="promise checks failed"):
        complete_task(0, diff=fake, path=p)


# --- status ---


def test_status_shows_all_tasks(promise_file: Path):
    output = status(promise_file)
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
    output = status(p)
    assert "1/2 completed" in output


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
                dependencies=["H0"],
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
    assert "Deps:   H0" in output


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
    assert task_dict["max_attempts"] == 3


def test_make_task_overrides():
    task_dict = make_task(
        title="custom", expected_lines_added=200, completed=True, max_attempts=5
    )
    assert task_dict["title"] == "custom"
    assert task_dict["expected_lines_added"] == 200
    assert task_dict["completed"] is True
    assert task_dict["max_attempts"] == 5


# --- _task_from_dict ---


def test_task_from_dict_empty_dict_defaults():
    """All defaults are correct when dict is empty."""
    task = _task_from_dict({})
    assert task.title == ""
    assert (
        task.task_id == ""
    )  # No backfill at _task_from_dict level; load_promise handles it
    assert task.goal == ""
    assert task.success_criteria == ""
    assert task.files_to_create == []
    assert task.files_to_modify == []
    assert task.files_to_remove == []
    assert task.expected_lines_added == 0
    assert task.expected_lines_removed == 0
    assert task.context_files == []
    assert task.doc_sections == []
    assert task.reference_skills == []
    assert task.dependencies == []
    assert task.completed is False
    assert task.max_attempts == 3
    assert task.attempts == 0


def test_task_from_dict_reads_each_key():
    """Every key in the dict is correctly assigned to the right field."""
    d = {
        "title": "My Task",
        "task_id": "abc123def456",
        "goal": "My Goal",
        "success_criteria": "It works",
        "files_to_create": ["a.py"],
        "files_to_modify": ["b.py"],
        "files_to_remove": ["c.py"],
        "expected_lines_added": 42,
        "expected_lines_removed": 7,
        "context_files": ["ctx.py"],
        "doc_sections": ["DESIGN.md#API"],
        "reference_skills": ["tech-fastapi"],
        "dependencies": ["H0", "H1"],
        "completed": True,
        "max_attempts": 5,
        "attempts": 2,
    }
    task = _task_from_dict(d)
    assert task.title == "My Task"
    assert task.task_id == "abc123def456"
    assert task.goal == "My Goal"
    assert task.success_criteria == "It works"
    assert task.files_to_create == ["a.py"]
    assert task.files_to_modify == ["b.py"]
    assert task.files_to_remove == ["c.py"]
    assert task.expected_lines_added == 42
    assert task.expected_lines_removed == 7
    assert task.context_files == ["ctx.py"]
    assert task.doc_sections == ["DESIGN.md#API"]
    assert task.reference_skills == ["tech-fastapi"]
    assert task.dependencies == ["H0", "H1"]
    assert task.completed is True
    assert task.max_attempts == 5
    assert task.attempts == 2


def test_task_from_dict_list_wrapping():
    """list() wrapping converts non-list iterables to lists."""
    d = {
        "title": "t",
        "files_to_create": ("a.py",),
        "files_to_modify": ("b.py",),
        "files_to_remove": ("c.py",),
        "context_files": ("ctx.py",),
        "doc_sections": ("sec",),
        "reference_skills": ("skill",),
        "dependencies": ("H0",),
    }
    task = _task_from_dict(d)
    assert isinstance(task.files_to_create, list)
    assert isinstance(task.files_to_modify, list)
    assert isinstance(task.files_to_remove, list)
    assert isinstance(task.context_files, list)
    assert isinstance(task.doc_sections, list)
    assert isinstance(task.reference_skills, list)
    assert isinstance(task.dependencies, list)


# --- _metadata_from_dict ---


def test_metadata_from_dict_empty_dict_defaults():
    meta = _metadata_from_dict({})
    assert meta.base_commit == ""
    assert meta.created_at == ""


def test_metadata_from_dict_reads_each_key():
    meta = _metadata_from_dict({"base_commit": "abc123", "created_at": "2025-01-01"})
    assert meta.base_commit == "abc123"
    assert meta.created_at == "2025-01-01"


def test_metadata_from_dict_partial_keys():
    """Only base_commit provided; created_at defaults."""
    meta = _metadata_from_dict({"base_commit": "abc123"})
    assert meta.base_commit == "abc123"
    assert meta.created_at == ""


# --- _task_to_dict ---


def test_task_to_dict_all_keys_present():
    task = Task(
        title="T",
        task_id="test_id_123",
        goal="G",
        success_criteria="SC",
        files_to_create=["a"],
        files_to_modify=["b"],
        files_to_remove=["c"],
        expected_lines_added=10,
        expected_lines_removed=5,
        context_files=["ctx"],
        doc_sections=["doc"],
        reference_skills=["skill"],
        dependencies=["H0"],
        completed=True,
        attempts=2,
        max_attempts=5,
    )
    d = _task_to_dict(task)
    assert d["title"] == "T"
    assert d["task_id"] == "test_id_123"
    assert d["goal"] == "G"
    assert d["success_criteria"] == "SC"
    assert d["files_to_create"] == ["a"]
    assert d["files_to_modify"] == ["b"]
    assert d["files_to_remove"] == ["c"]
    assert d["expected_lines_added"] == 10
    assert d["expected_lines_removed"] == 5
    assert d["context_files"] == ["ctx"]
    assert d["doc_sections"] == ["doc"]
    assert d["reference_skills"] == ["skill"]
    assert d["dependencies"] == ["H0"]
    assert d["completed"] is True
    assert d["attempts"] == 2
    assert d["max_attempts"] == 5


def test_task_to_dict_does_not_swap_attempts_and_max_attempts():
    """attempts and max_attempts map to the correct keys."""
    task = Task(title="T", attempts=1, max_attempts=7)
    d = _task_to_dict(task)
    assert d["attempts"] == 1
    assert d["max_attempts"] == 7


# --- load_promise edge cases ---


def test_load_promise_empty_file(tmp_path: Path):
    """Loading a TOML with no sections gives empty promise."""
    p = tmp_path / "empty.toml"
    p.write_text("")
    promise = load_promise(p)
    assert promise.tasks == []
    assert promise.metadata.base_commit == ""
    assert promise.metadata.created_at == ""


def test_load_promise_metadata_only(tmp_path: Path):
    """Loading TOML with metadata but no tasks."""
    p = tmp_path / "meta.toml"
    p.write_text('[metadata]\nbase_commit = "deadbeef"\ncreated_at = "2025-01-01"\n')
    promise = load_promise(p)
    assert promise.metadata.base_commit == "deadbeef"
    assert promise.metadata.created_at == "2025-01-01"
    assert promise.tasks == []


# --- save_promise conditional metadata ---


def test_save_promise_omits_empty_base_commit(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="", created_at="2025-01-01"))
    path = tmp_path / "p.toml"
    save_promise(p, path)
    content = path.read_text()
    assert "base_commit" not in content
    assert "created_at" in content


def test_save_promise_omits_empty_created_at(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="abc", created_at=""))
    path = tmp_path / "p.toml"
    save_promise(p, path)
    content = path.read_text()
    assert "base_commit" in content
    assert "created_at" not in content


def test_save_promise_includes_all_task_fields(tmp_path: Path):
    """Every task field appears in the serialized TOML."""
    task = Task(
        title="T",
        goal="G",
        files_to_create=["a.py"],
        files_to_modify=["b.py"],
        expected_lines_added=10,
        completed=True,
        attempts=2,
        max_attempts=5,
    )
    p = Promise(metadata=Metadata(), tasks=[task])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    content = path.read_text()
    assert "title" in content
    assert "goal" in content
    assert "files_to_create" in content
    assert "completed" in content
    assert "attempts" in content
    assert "max_attempts" in content


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
    """lines_added sums over files_to_create + files_to_modify."""
    task = Task(
        title="T",
        files_to_create=["new.py"],
        files_to_modify=["mod.py"],
        expected_lines_added=100,
    )
    diff = FakeGitDiff(stats={"new.py": (60, 0), "mod.py": (40, 10)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    assert added.status is CheckStatus.PASS  # 60 + 40 = 100


def test_check_line_counts_remove_files_includes_modify_and_remove():
    """lines_removed sums over files_to_modify + files_to_remove."""
    task = Task(
        title="T",
        files_to_modify=["mod.py"],
        files_to_remove=["old.py"],
        expected_lines_removed=50,
    )
    diff = FakeGitDiff(stats={"mod.py": (10, 30), "old.py": (0, 20)})
    results = _check_line_counts(task, diff, "HEAD")
    removed = next(r for r in results if r.name == "lines_removed")
    assert removed.status is CheckStatus.PASS  # 30 + 20 = 50


def test_check_line_counts_reads_correct_tuple_index():
    """added reads index [0], removed reads index [1] from numstat."""
    task = Task(
        title="T",
        files_to_create=["f.py"],
        files_to_remove=["g.py"],
        expected_lines_added=100,
        expected_lines_removed=50,
    )
    # f.py: 100 added, 999 removed; g.py: 999 added, 50 removed
    # If indices are swapped, the check would fail
    diff = FakeGitDiff(stats={"f.py": (100, 999), "g.py": (999, 50)})
    results = _check_line_counts(task, diff, "HEAD")
    added = next(r for r in results if r.name == "lines_added")
    removed = next(r for r in results if r.name == "lines_removed")
    assert added.status is CheckStatus.PASS
    assert removed.status is CheckStatus.PASS


def test_check_line_counts_missing_file_defaults_to_zero():
    """Files not in numstat contribute (0, 0)."""
    task = Task(
        title="T",
        files_to_create=["missing.py"],
        expected_lines_added=0,
        expected_lines_removed=0,
    )
    results = _check_line_counts(task, FakeGitDiff(stats={}), "HEAD")
    # expected_lines_added is 0, so it should be skipped
    added = next(r for r in results if r.name == "lines_added")
    assert added.status is CheckStatus.SKIP


def test_check_line_counts_only_create_files_no_modify():
    """Only files_to_create, no modify -- remove should be skipped."""
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
    """Only files_to_remove, no modify -- add should be skipped."""
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
    # index 2 is out of range for 2 tasks (0-1)
    with pytest.raises(PromiseError, match=r"Task index 2 out of range \(0-1\)"):
        check_task(2, diff=FakeGitDiff(), path=path)


def test_check_task_defaults_to_head_when_no_base_commit(tmp_path: Path):
    p = Promise(
        metadata=Metadata(base_commit=""),
        tasks=[Task(title="T", files_to_modify=["a.py"])],
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)

    captured: list[str] = []

    class CapturingDiff:
        def diff_names(self, base_commit: str, *paths: str) -> set[str]:
            captured.append(base_commit)
            return {"a.py"}

        def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat:
            captured.append(base_commit)
            return {}

    check_task(0, diff=CapturingDiff(), path=path)
    assert all(c == "HEAD" for c in captured)


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
            assert c.detail in ("none declared", "none expected")


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
    """expected_lines_added=1 should NOT be skipped (kills <= 0 → <= 1)."""
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
    """expected_lines_removed=1 should NOT be skipped (kills <= 0 → <= 1)."""
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
    # with expected=1 and actual=0, within tolerance (abs tolerance 30) → PASS
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
    """Status output uses exact [✓] and [✗] brackets."""
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
    """check_task without explicit diff= arg instantiates SubprocessGitDiff
    (kills diff=None).
    """
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
    """check_task only requests diffs for files relevant to the task."""
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
        # Verify that FakeGitDiff was called with scoped paths
        assert set(fake_diff.last_diff_names_paths) == {"src/app.py"}
        # sorted(['src/app.py', 'src/new.py', 'src/old.py'])
        assert list(fake_diff.last_diff_numstat_paths) == [
            "src/app.py",
            "src/new.py",
            "src/old.py",
        ]

        # Verify line counts only include task files
        added_check = next(c for c in report.checks if c.name == "lines_added")
        assert "actual 10" in added_check.detail  # 5 from app.py + 5 from new.py
        removed_check = next(c for c in report.checks if c.name == "lines_removed")
        assert "actual 5" in removed_check.detail  # 5 from app.py
    finally:
        os.chdir(old_cwd)
