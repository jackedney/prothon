"""Promise data model, TOML I/O, git diff verification."""

from __future__ import annotations

import fcntl
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator

import tomlkit
import tomlkit.exceptions

from prothon.exceptions import PromiseError
from prothon.git import GitDiffProvider, SubprocessGitDiff

PROMISE_PATH = Path("docs/change_promise.toml")
DEFAULT_TOLERANCE = 30


@contextmanager
def _lock_promise(path: Path) -> Iterator[None]:
    """Acquire an exclusive file lock on the promise file.

    Uses a sibling .lock file so the promise TOML can be fully rewritten
    without interfering with the lock.
    """
    lock_path = path.with_suffix(".toml.lock")
    lock_path.touch(exist_ok=True)
    fd = lock_path.open("w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


class CheckStatus(Enum):
    """Tri-state result for a single verification check."""

    PASSED = "PASS"
    FAILED = "FAIL"
    SKIPPED = "SKIP"


@dataclass
class FileCheckDetail:
    """Per-file pass/fail detail within a check."""

    path: str
    expected_state: str
    actual_state: str
    status: CheckStatus


@dataclass
class CheckResult:
    """Single verification check result."""

    name: str
    status: CheckStatus
    detail: str
    file_details: list[FileCheckDetail] = field(default_factory=list)


@dataclass
class TaskCheckReport:
    """Aggregated verification report for one task."""

    task_index: int
    title: str
    task_id: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(c.status is CheckStatus.FAILED for c in self.checks)

    def format(self) -> str:
        """Return a human-readable summary of the check results."""
        overall = "PASS" if self.passed else "DISCREPANCY"
        failures = sum(1 for c in self.checks if c.status is CheckStatus.FAILED)
        lines = [f'TASK {self.task_index}: "{self.title}"']
        for c in self.checks:
            lines.append(f"  {c.name + ':':20s} {c.status.value} ({c.detail})")
        suffix = (
            ""
            if self.passed
            else f" ({failures} failure{'s' if failures != 1 else ''})"
        )
        lines.append(f"  RESULT: {overall}{suffix}")
        return "\n".join(lines)


@dataclass
class Task:
    """A single promised task within the change promise."""

    title: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    goal: str = ""
    success_criteria: str = ""
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    files_to_remove: list[str] = field(default_factory=list)
    expected_lines_added: int = 0
    expected_lines_removed: int = 0
    context_files: list[str] = field(default_factory=list)
    doc_sections: list[str] = field(default_factory=list)
    reference_skills: list[str] = field(default_factory=list)
    dependencies: list[int] = field(default_factory=list)
    completed: bool = False
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class Metadata:
    """Promise-level metadata (base commit, timestamps, etc.)."""

    base_commit: str = ""
    created_at: str = ""


@dataclass
class Promise:
    """Top-level change promise containing metadata and tasks."""

    metadata: Metadata = field(default_factory=Metadata)
    tasks: list[Task] = field(default_factory=list)


def _task_from_dict(d: dict) -> Task:
    """Construct a Task from a TOML dict, tolerating missing keys."""
    return Task(
        title=d.get("title", ""),
        task_id=d.get("task_id") or uuid.uuid4().hex,
        goal=d.get("goal", ""),
        success_criteria=d.get("success_criteria", ""),
        files_to_create=list(d.get("files_to_create", [])),
        files_to_modify=list(d.get("files_to_modify", [])),
        files_to_remove=list(d.get("files_to_remove", [])),
        expected_lines_added=d.get("expected_lines_added", 0),
        expected_lines_removed=d.get("expected_lines_removed", 0),
        context_files=list(d.get("context_files", [])),
        doc_sections=list(d.get("doc_sections", [])),
        reference_skills=list(d.get("reference_skills", [])),
        dependencies=list(d.get("dependencies", [])),
        completed=d.get("completed", False),
        max_attempts=d.get("max_attempts", 3),
        attempts=d.get("attempts", 0),
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
    return Promise(metadata=metadata, tasks=tasks)


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

    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def _within_tolerance(expected: int, actual: int) -> bool:
    """Check if actual is within +/-30% or +/-30 lines of expected (whichever is greater)."""
    pct_tolerance = expected * 0.3
    abs_tolerance = DEFAULT_TOLERANCE
    tolerance = int(max(pct_tolerance, abs_tolerance))
    return abs(actual - expected) <= tolerance


def _check_line_count(name: str, expected: int, actual: int) -> CheckResult:
    """Build a CheckResult for a line-count metric."""
    ok = _within_tolerance(expected, actual)
    status = CheckStatus.PASSED if ok else CheckStatus.FAILED
    detail = f"expected ~{expected}, actual {actual}"
    if not ok:
        detail += " \u2014 outside \u00b130%/\u00b130 tolerance"
    return CheckResult(name=name, status=status, detail=detail)


def _check_line_counts(
    task: Task, diff: GitDiffProvider, base_commit: str
) -> list[CheckResult]:
    """Check added/removed line counts against tolerances."""
    add_files = set(task.files_to_create + task.files_to_modify)
    remove_files = set(task.files_to_modify + task.files_to_remove)

    results: list[CheckResult] = []
    numstat = diff.diff_numstat(base_commit)

    if not add_files or task.expected_lines_added <= 0:
        results.append(
            CheckResult(
                name="lines_added", status=CheckStatus.SKIPPED, detail="none expected"
            )
        )
    else:
        actual_added = sum(numstat.get(f, (0, 0))[0] for f in add_files)
        results.append(
            _check_line_count("lines_added", task.expected_lines_added, actual_added)
        )

    if not remove_files or task.expected_lines_removed <= 0:
        results.append(
            CheckResult(
                name="lines_removed", status=CheckStatus.SKIPPED, detail="none expected"
            )
        )
    else:
        actual_removed = sum(numstat.get(f, (0, 0))[1] for f in remove_files)
        results.append(
            _check_line_count(
                "lines_removed", task.expected_lines_removed, actual_removed
            )
        )

    return results


def check_task(
    task_index: int,
    *,
    diff: GitDiffProvider | None = None,
    path: Path = PROMISE_PATH,
) -> TaskCheckReport:
    """Check a single task's promises against git reality.

    Args:
        task_index: Zero-based index of the task to check.
        diff: Git diff data source; defaults to SubprocessGitDiff().
        path: Path to the promise TOML file.

    Returns:
        A TaskCheckReport with per-check PASS/FAIL details.

    Raises:
        PromiseError: If task_index is out of range.
    """
    if diff is None:
        diff = SubprocessGitDiff()

    promise = load_promise(path)
    if task_index < 0 or task_index >= len(promise.tasks):
        if not promise.tasks:
            msg = f"Task index {task_index} out of range (no tasks in promise)"
        else:
            msg = f"Task index {task_index} out of range (0-{len(promise.tasks) - 1})"
        raise PromiseError(msg)

    base_commit = promise.metadata.base_commit or "HEAD"
    task = promise.tasks[task_index]
    report = TaskCheckReport(
        task_index=task_index, title=task.title, task_id=task.task_id
    )

    # Check files_to_create
    if task.files_to_create:
        existing = [f for f in task.files_to_create if Path(f).exists()]
        all_exist = len(existing) == len(task.files_to_create)
        report.checks.append(
            CheckResult(
                name="files_to_create",
                status=CheckStatus.PASSED if all_exist else CheckStatus.FAILED,
                detail=f"{len(existing)}/{len(task.files_to_create)} exist",
            )
        )
    else:
        report.checks.append(
            CheckResult(
                name="files_to_create",
                status=CheckStatus.SKIPPED,
                detail="none declared",
            )
        )

    # Check files_to_modify
    if task.files_to_modify:
        diff_names = diff.diff_names(base_commit)
        modified = [f for f in task.files_to_modify if f in diff_names]
        all_modified = len(modified) == len(task.files_to_modify)
        report.checks.append(
            CheckResult(
                name="files_to_modify",
                status=CheckStatus.PASSED if all_modified else CheckStatus.FAILED,
                detail=f"{len(modified)}/{len(task.files_to_modify)} modified",
            )
        )
    else:
        report.checks.append(
            CheckResult(
                name="files_to_modify",
                status=CheckStatus.SKIPPED,
                detail="none declared",
            )
        )

    # Check files_to_remove
    if task.files_to_remove:
        removed = [f for f in task.files_to_remove if not Path(f).exists()]
        all_removed = len(removed) == len(task.files_to_remove)
        report.checks.append(
            CheckResult(
                name="files_to_remove",
                status=CheckStatus.PASSED if all_removed else CheckStatus.FAILED,
                detail=f"{len(removed)}/{len(task.files_to_remove)} removed",
            )
        )
    else:
        report.checks.append(
            CheckResult(
                name="files_to_remove",
                status=CheckStatus.SKIPPED,
                detail="none declared",
            )
        )

    # Check line counts
    report.checks.extend(_check_line_counts(task, diff, base_commit))

    return report


def complete_task(
    task_index: int,
    *,
    attempts: int = 1,
    diff: GitDiffProvider | None = None,
    path: Path = PROMISE_PATH,
) -> None:
    """Mark a task as completed after verifying its promises pass.

    Runs ``check_task`` first and refuses to mark the task complete if
    any check fails (SPEC R34: compliance mandatory before completion).

    Args:
        task_index: Zero-based index of the task to mark complete.
        attempts: Number of attempts taken to complete the task.
        diff: Git diff data source; defaults to SubprocessGitDiff().
        path: Path to the promise TOML file.

    Raises:
        PromiseError: If task_index is out of range or checks fail.
    """
    report = check_task(task_index, diff=diff, path=path)
    if not report.passed:
        raise PromiseError(
            f"Task {task_index} cannot be completed: promise checks failed"
        )
    # Lock the promise file so parallel completions don't overwrite each other.
    with _lock_promise(path):
        promise = load_promise(path)
        if task_index < 0 or task_index >= len(promise.tasks):
            raise PromiseError(
                f"Task index {task_index} out of range after re-load; "
                "promise file may have changed — re-run `promise check` and retry"
            )
        if promise.tasks[task_index].task_id != report.task_id:
            raise PromiseError(
                f"Task {task_index} identity changed between check and completion "
                f"(expected task_id {report.task_id!r}, got {promise.tasks[task_index].task_id!r}); "
                "re-run `promise check` and retry"
            )
        promise.tasks[task_index].completed = True
        promise.tasks[task_index].attempts = attempts
        save_promise(promise, path)


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
