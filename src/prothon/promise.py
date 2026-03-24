"""Promise data model, TOML I/O, git diff verification."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import tomlkit
import tomlkit.exceptions

from prothon.exceptions import PromiseError
from prothon.git import GitDiffProvider
from prothon.models import PROMISE_PATH, Metadata, Promise, Task, _generate_id


if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def _lock_promise(path: Path) -> Iterator[None]:
        """Acquire an exclusive file lock on the promise file (Windows)."""
        lock_path = path.with_suffix(".toml.lock")
        if not lock_path.exists() or lock_path.stat().st_size == 0:
            lock_path.write_bytes(b"\0")
        with lock_path.open("r+b") as fd:
            msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    @contextmanager
    def _lock_promise(path: Path) -> Iterator[None]:
        """Acquire an exclusive file lock on the promise file (Unix)."""
        lock_path = path.with_suffix(".toml.lock")
        lock_path.touch(exist_ok=True)
        with lock_path.open("w") as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)


def _coerce_int(value: object, field: str) -> int:
    """Coerce a TOML value to int, raising PromiseError on failure."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise PromiseError(
            f"field '{field}' must be an integer, got {type(value).__name__}: {value!r}"
        ) from None


def _task_from_dict(d: dict) -> Task:
    """Construct a Task from a TOML dict, requiring task_id."""
    return Task(
        title=d.get("title", ""),
        task_id=d.get("task_id", ""),
        goal=d.get("goal", ""),
        success_criteria=d.get("success_criteria", ""),
        files_to_create=list(d.get("files_to_create", [])),
        files_to_modify=list(d.get("files_to_modify", [])),
        files_to_remove=list(d.get("files_to_remove", [])),
        expected_lines_added=_coerce_int(
            d.get("expected_lines_added", 0), "expected_lines_added"
        ),
        expected_lines_removed=_coerce_int(
            d.get("expected_lines_removed", 0), "expected_lines_removed"
        ),
        context_files=list(d.get("context_files", [])),
        doc_sections=list(d.get("doc_sections", [])),
        reference_skills=list(d.get("reference_skills", [])),
        dependencies=list(d.get("dependencies", [])),
        completed=d.get("completed", False),
        max_attempts=_coerce_int(d.get("max_attempts", 3), "max_attempts"),
        attempts=_coerce_int(d.get("attempts", 0), "attempts"),
    )


def _metadata_from_dict(d: dict) -> Metadata:
    """Construct a Metadata from a TOML dict, tolerating missing keys."""
    return Metadata(
        base_commit=d.get("base_commit", ""),
        created_at=d.get("created_at", ""),
    )


def _task_to_dict(task: Task) -> dict:
    """Serialize a Task to a plain dict for TOML output."""
    return {
        "title": task.title,
        "task_id": task.task_id,
        "goal": task.goal,
        "success_criteria": task.success_criteria,
        "files_to_create": task.files_to_create,
        "files_to_modify": task.files_to_modify,
        "files_to_remove": task.files_to_remove,
        "expected_lines_added": task.expected_lines_added,
        "expected_lines_removed": task.expected_lines_removed,
        "context_files": task.context_files,
        "doc_sections": task.doc_sections,
        "reference_skills": task.reference_skills,
        "dependencies": task.dependencies,
        "completed": task.completed,
        "attempts": task.attempts,
        "max_attempts": task.max_attempts,
    }


def load_promise(path: Path = PROMISE_PATH) -> Promise:
    """Load a change promise from a TOML file.

    Args:
        path: Path to the promise TOML file.

    Returns:
        A Promise dataclass populated from the file.
    """
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PromiseError(f"promise file not found: {path}") from None
    except tomlkit.exceptions.ParseError as exc:
        raise PromiseError(f"malformed TOML in {path}: {exc}") from exc
    metadata = _metadata_from_dict(dict(doc.get("metadata", {})))
    tasks = [_task_from_dict(dict(t)) for t in doc.get("tasks", [])]
    promise = Promise(metadata=metadata, tasks=tasks)

    # Backfill missing task_ids and persist them so subsequent loads are stable.
    needs_backfill = [i for i, t in enumerate(promise.tasks) if not t.task_id]
    if needs_backfill:
        with _lock_promise(path):
            for i in needs_backfill:
                new_id = _generate_id()
                promise.tasks[i].task_id = new_id
                _update_task_fields(path, i, {"task_id": new_id})

    return promise


def save_promise(promise: Promise, path: Path = PROMISE_PATH) -> None:
    """Serialize a Promise dataclass to TOML and write to disk.

    Args:
        promise: The Promise to save.
        path: Path to write the TOML file.
    """
    doc = tomlkit.document()

    meta = tomlkit.table()
    if promise.metadata.base_commit:
        meta.add("base_commit", promise.metadata.base_commit)
    if promise.metadata.created_at:
        meta.add("created_at", promise.metadata.created_at)
    doc.add("metadata", meta)

    tasks_aot = tomlkit.aot()
    for task in promise.tasks:
        tbl = tomlkit.table()
        for key, value in _task_to_dict(task).items():
            tbl.add(key, value)
        tasks_aot.append(tbl)
    doc.add("tasks", tasks_aot)

    content = tomlkit.dumps(doc)
    data = content.encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise
    os.close(fd)
    try:
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def complete_task(
    task_index: int,
    *,
    diff: GitDiffProvider | None = None,
    path: Path = PROMISE_PATH,
) -> None:
    """Mark a task as completed after verifying its promises pass.

    Runs ``check_task`` first and refuses to mark the task complete if
    any check fails (SPEC R34: compliance mandatory before completion).

    The persisted ``attempts`` counter (incremented by ``record_attempt``)
    is preserved as-is — this function does not overwrite it.

    Args:
        task_index: Zero-based index of the task to mark complete.
        diff: Git diff data source; defaults to SubprocessGitDiff().
        path: Path to the promise TOML file.

    Raises:
        PromiseError: If task_index is out of range or checks fail.
    """
    from prothon.promise_verify import check_task

    report = check_task(task_index, diff=diff, path=path)
    if not report.passed:
        raise PromiseError(
            f"Task {task_index} cannot be completed: promise checks failed"
        )
    with _lock_promise(path):
        promise = load_promise(path)
        if task_index < 0 or task_index >= len(promise.tasks):
            raise PromiseError(
                f"Task index {task_index} out of range after re-load; "
                "promise file may have changed — re-run `promise check` and retry"
            )
        if not report.task_id:
            raise PromiseError(f"Task {task_index} is missing a task_id")
        if promise.tasks[task_index].task_id != report.task_id:
            raise PromiseError(
                f"Task {task_index} identity changed between check and completion "
                f"(expected task_id {report.task_id!r}, "
                f"got {promise.tasks[task_index].task_id!r}); "
                "re-run `promise check` and retry"
            )
        if promise.tasks[task_index].completed:
            return
        promise.tasks[task_index].completed = True
        _update_task_fields(path, task_index, {"completed": True})


def _update_task_fields(path: Path, task_index: int, updates: dict) -> None:
    """Mutate specific task fields in the TOML file, preserving comments and formatting.

    Must be called while ``_lock_promise`` is held.
    """
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PromiseError(f"promise file not found: {path}") from None
    tasks = doc.get("tasks", [])
    if task_index < 0 or task_index >= len(tasks):
        raise PromiseError(
            f"Task index {task_index} out of range; promise file may have changed"
        )
    for key, value in updates.items():
        tasks[task_index][key] = value
    content = tomlkit.dumps(doc)
    data = content.encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise
    os.close(fd)
    try:
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def record_attempt(
    task_index: int,
    *,
    path: Path = PROMISE_PATH,
) -> None:
    """Increment the attempt counter for a task.

    Args:
        task_index: Zero-based index of the task.
        path: Path to the promise TOML file.

    Raises:
        PromiseError: If task_index is out of range or attempts is not an integer.
    """
    with _lock_promise(path):
        promise = load_promise(path)
        if task_index < 0 or task_index >= len(promise.tasks):
            raise PromiseError(
                f"Task index {task_index} out of range; promise file may have changed"
            )
        new_attempts = promise.tasks[task_index].attempts + 1
        _update_task_fields(path, task_index, {"attempts": new_attempts})


def status(path: Path = PROMISE_PATH) -> str:
    """Return a formatted status of all tasks."""
    promise = load_promise(path)
    lines = []
    for i, task in enumerate(promise.tasks):
        mark = "\u2713" if task.completed else "\u2717"
        lines.append(f"  [{mark}] {i}: {task.title}")
    done = sum(1 for t in promise.tasks if t.completed)
    lines.append(f"\n  {done}/{len(promise.tasks)} completed")
    return "\n".join(lines)


def _format_task_plan(index: int, task: Task) -> list[str]:
    """Format a single task for the plan view."""
    lines = [f"Task {index}: {task.title}"]
    if task.goal:
        lines.append(f"  Goal:   {task.goal}")

    _optional_list = [
        ("Create", task.files_to_create),
        ("Modify", task.files_to_modify),
        ("Remove", task.files_to_remove),
        ("Reads", task.context_files),
        ("Skills", task.reference_skills),
        ("Docs", task.doc_sections),
    ]
    for label, items in _optional_list:
        if items:
            lines.append(f"  {label + ':':8s}{', '.join(items)}")

    if task.dependencies:
        dep_labels = [f"Task {d}" for d in task.dependencies]
        lines.append(f"  Deps:   {', '.join(dep_labels)}")
    else:
        lines.append("  Deps:   none")

    lines.append(
        f"  Lines:  +{task.expected_lines_added} / -{task.expected_lines_removed}"
    )
    lines.append("")
    return lines


def plan(path: Path = PROMISE_PATH) -> str:
    """Return a formatted plan view of all tasks for human review."""
    promise = load_promise(path)
    base = promise.metadata.base_commit or "unknown"
    task_word = "task" if len(promise.tasks) == 1 else "tasks"
    lines = [f"PLAN: {len(promise.tasks)} {task_word} (base: {base})", ""]

    for i, task in enumerate(promise.tasks):
        lines.extend(_format_task_plan(i, task))

    return "\n".join(lines)


def cleanup(path: Path = PROMISE_PATH) -> None:
    """Remove the promise file after all tasks are complete."""
    path.unlink()
