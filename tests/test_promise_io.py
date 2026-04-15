"""Tests for promise TOML load/save and serialization helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from prothon.exceptions import PromiseError
from prothon.git import DiffStat
from prothon.models import Metadata, Promise, Task
from prothon.promise import (
    _metadata_from_dict,
    _task_from_dict,
    _task_to_dict,
    cleanup,
    load_promise,
    plan,
    save_promise,
)
from prothon.promise_verify import check_task


@pytest.fixture(autouse=True)
def mock_pre_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prothon.promise_verify.run_pre_commit", lambda _p, **_k: (0, "Passed")
    )


def test_load_promise_missing_file_raises_promise_error(tmp_path: Path):
    with pytest.raises(PromiseError, match="promise file not found"):
        load_promise(tmp_path / "nonexistent.toml")


def test_load_promise_malformed_toml_raises_promise_error(tmp_path: Path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[invalid toml\n")
    with pytest.raises(PromiseError, match="malformed TOML"):
        load_promise(bad)


def test_load_save_roundtrip(tmp_path: Path):
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
    loaded = load_promise(p)
    assert loaded.tasks[0].title == "Add auth module"
    assert len(loaded.tasks) == 2
    assert loaded.tasks[0].max_attempts == 3
    loaded.tasks[0].completed = True
    loaded.tasks[0].max_attempts = 5
    save_promise(loaded, p)
    reloaded = load_promise(p)
    assert reloaded.tasks[0].completed is True
    assert reloaded.tasks[0].max_attempts == 5
    assert reloaded.tasks[1].completed is False


def test_load_save_roundtrip_preserves_metadata(tmp_path: Path):
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
    loaded = load_promise(p)
    assert loaded.metadata.base_commit == "abc1234"
    save_promise(loaded, p)
    assert load_promise(p).metadata.base_commit == "abc1234"


def test_task_from_dict_coerces_string_attempts():
    with pytest.raises(PromiseError, match="must be an integer"):
        _task_from_dict({"title": "Bad", "attempts": "zero"})


def test_task_from_dict_empty_dict_defaults():
    task = _task_from_dict({})
    assert task.title == ""
    assert task.task_id == ""
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


def test_metadata_from_dict_empty_dict_defaults():
    meta = _metadata_from_dict({})
    assert meta.base_commit == ""
    assert meta.created_at == ""


def test_metadata_from_dict_reads_each_key():
    meta = _metadata_from_dict({"base_commit": "abc123", "created_at": "2025-01-01"})
    assert meta.base_commit == "abc123"
    assert meta.created_at == "2025-01-01"


def test_metadata_from_dict_partial_keys():
    meta = _metadata_from_dict({"base_commit": "abc123"})
    assert meta.base_commit == "abc123"
    assert meta.created_at == ""


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
    task = Task(title="T", attempts=1, max_attempts=7)
    d = _task_to_dict(task)
    assert d["attempts"] == 1
    assert d["max_attempts"] == 7


def test_load_promise_empty_file(tmp_path: Path):
    p = tmp_path / "empty.toml"
    p.write_text("")
    promise = load_promise(p)
    assert promise.tasks == []
    assert promise.metadata.base_commit == ""
    assert promise.metadata.created_at == ""


def test_load_promise_metadata_only(tmp_path: Path):
    p = tmp_path / "meta.toml"
    p.write_text('[metadata]\nbase_commit = "deadbeef"\ncreated_at = "2025-01-01"\n')
    promise = load_promise(p)
    assert promise.metadata.base_commit == "deadbeef"
    assert promise.metadata.created_at == "2025-01-01"
    assert promise.tasks == []


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


def test_save_promise_created_at_key_name(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="abc", created_at="2025-01-01"))
    path = tmp_path / "p.toml"
    save_promise(p, path)
    content = path.read_text()
    assert "created_at" in content
    assert load_promise(path).metadata.created_at == "2025-01-01"


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
            Task(title="Task A", goal="First", expected_lines_added=10),
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


def test_plan_singular_task_word(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    output = plan(path)
    assert "1 task " in output or "1 task\n" in output or output.endswith("1 task")
    assert "1 tasks" not in output


def test_plan_plural_tasks_word(tmp_path: Path):
    p = Promise(
        metadata=Metadata(base_commit="abc"), tasks=[Task(title="T1"), Task(title="T2")]
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "2 tasks" in plan(path)


def test_plan_unknown_base_when_empty(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit=""), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "unknown" in plan(path)


def test_plan_no_deps_shows_none(tmp_path: Path):
    p = Promise(
        metadata=Metadata(base_commit="abc"), tasks=[Task(title="No deps task")]
    )
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "Deps:   none" in plan(path)


def test_plan_lines_joined_with_newline(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "XX" not in plan(path)


def test_plan_has_blank_line_after_header(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit="abc"), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert plan(path).split("\n")[1] == ""


def test_plan_exact_unknown_string(tmp_path: Path):
    p = Promise(metadata=Metadata(base_commit=""), tasks=[Task(title="T")])
    path = tmp_path / "p.toml"
    save_promise(p, path)
    assert "(base: unknown)" in plan(path)


def test_cleanup_removes_promise_file(tmp_path: Path):
    p = tmp_path / "promise.toml"
    save_promise(Promise(), p)
    assert p.exists()
    cleanup(p)
    assert not p.exists()


def test_cleanup_raises_if_file_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        cleanup(tmp_path / "promise.toml")


# --- check_task with TOML serialization ---


def test_check_task_passes_base_commit_to_diff_provider(tmp_path: Path):
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
