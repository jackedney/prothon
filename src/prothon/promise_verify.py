"""Git diff analysis and task verification logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from prothon.compliance import CheckStatus
from prothon.exceptions import PromiseError
from prothon.git import GitDiffProvider, SubprocessGitDiff, run_pre_commit
from prothon.models import Promise, Task

DEFAULT_TOLERANCE = 30


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
        return not any(c.status is CheckStatus.FAIL for c in self.checks)

    def format(self) -> str:
        """Return a human-readable summary of the check results."""
        overall = "PASS" if self.passed else "DISCREPANCY"
        failures = sum(1 for c in self.checks if c.status is CheckStatus.FAIL)
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


def _within_tolerance(expected: int, actual: int) -> bool:
    """Check if actual is within +/-30% or +/-30 lines of expected.

    The greater of 30% or 30 lines is used as the tolerance.
    """
    pct_tolerance = expected * 0.3
    abs_tolerance = DEFAULT_TOLERANCE
    tolerance = int(max(pct_tolerance, abs_tolerance))
    return abs(actual - expected) <= tolerance


def _check_line_count(name: str, expected: int, actual: int) -> CheckResult:
    """Build a CheckResult for a line-count metric."""
    ok = _within_tolerance(expected, actual)
    status = CheckStatus.PASS if ok else CheckStatus.FAIL
    detail = f"expected ~{expected}, actual {actual}"
    if not ok:
        detail += " \u2014 outside \u00b130%/\u00b130 tolerance"
    return CheckResult(name=name, status=status, detail=detail)


def _check_line_counts(
    task: Task, diff: GitDiffProvider, base_commit: str
) -> list[CheckResult]:
    """Check added/removed line counts against tolerances."""
    add_files = {*task.files_to_create, *task.files_to_modify}
    remove_files = {*task.files_to_modify, *task.files_to_remove}
    all_task_files = add_files | remove_files

    results: list[CheckResult] = []
    numstat = diff.diff_numstat(base_commit, *sorted(all_task_files))

    if not add_files or task.expected_lines_added <= 0:
        results.append(
            CheckResult(
                name="lines_added", status=CheckStatus.SKIP, detail="none expected"
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
                name="lines_removed", status=CheckStatus.SKIP, detail="none expected"
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


def _validate_params(
    task_index: int,
    diff: GitDiffProvider | None,
    path: Path | None,
    promise: Promise | None,
) -> tuple[GitDiffProvider, Promise]:
    """Validate and resolve parameters for check_task."""
    resolved_diff = diff if diff is not None else SubprocessGitDiff()

    if promise is None:
        from prothon.promise import PROMISE_PATH, load_promise

        promise_path = path if path is not None else PROMISE_PATH
        promise = load_promise(promise_path)

    if task_index < 0 or task_index >= len(promise.tasks):
        if not promise.tasks:
            msg = f"Task index {task_index} out of range (no tasks in promise)"
        else:
            msg = f"Task index {task_index} out of range (0-{len(promise.tasks) - 1})"
        raise PromiseError(msg)

    return resolved_diff, promise


def check_task(
    task_index: int,
    *,
    diff: GitDiffProvider | None = None,
    path: Path | None = None,
    promise: Promise | None = None,
) -> TaskCheckReport:
    """Check a single task's promises against git reality."""
    diff, promise = _validate_params(task_index, diff, path, promise)

    if path is not None:
        promise_path = path
    else:
        from prothon.promise import PROMISE_PATH

        promise_path = PROMISE_PATH

    base_path = (
        promise_path.parent.parent
        if promise_path.parent.name == "docs"
        else promise_path.parent
    )

    base_commit = promise.metadata.base_commit or "HEAD"
    task = promise.tasks[task_index]
    report = TaskCheckReport(
        task_index=task_index, title=task.title, task_id=task.task_id
    )

    # Check files
    report.checks.append(_check_files_to_create(task, base_path))
    report.checks.append(_check_files_to_modify(task, diff, base_commit))
    report.checks.append(_check_files_to_remove(task, base_path))

    # Check line counts
    report.checks.extend(_check_line_counts(task, diff, base_commit))

    # SPEC R32: Run pre-commit hooks
    all_files = sorted({*task.files_to_create, *task.files_to_modify})
    if all_files:
        rc, output = run_pre_commit(all_files, cwd=base_path)
        status = CheckStatus.PASS if rc == 0 else CheckStatus.FAIL
        detail = "all hooks passed" if rc == 0 else "some hooks failed"
        report.checks.append(
            CheckResult(name="pre-commit", status=status, detail=detail)
        )

    return report


def _check_files_to_create(task: Task, base_path: Path) -> CheckResult:
    """Verify that all files declared for creation actually exist."""
    if not task.files_to_create:
        return CheckResult(
            name="files_to_create",
            status=CheckStatus.SKIP,
            detail="none declared",
        )
    existing = [
        f
        for f in task.files_to_create
        if (Path(f) if Path(f).is_absolute() else base_path / f).exists()
    ]
    all_exist = len(existing) == len(task.files_to_create)
    return CheckResult(
        name="files_to_create",
        status=CheckStatus.PASS if all_exist else CheckStatus.FAIL,
        detail=f"{len(existing)}/{len(task.files_to_create)} exist",
    )


def _check_files_to_modify(
    task: Task, diff: GitDiffProvider, base_commit: str
) -> CheckResult:
    """Verify that all files declared for modification are present in the git diff."""
    if not task.files_to_modify:
        return CheckResult(
            name="files_to_modify",
            status=CheckStatus.SKIP,
            detail="none declared",
        )
    diff_names = diff.diff_names(base_commit, *task.files_to_modify)
    modified = [f for f in task.files_to_modify if f in diff_names]
    all_modified = len(modified) == len(task.files_to_modify)
    return CheckResult(
        name="files_to_modify",
        status=CheckStatus.PASS if all_modified else CheckStatus.FAIL,
        detail=f"{len(modified)}/{len(task.files_to_modify)} modified",
    )


def _check_files_to_remove(task: Task, base_path: Path) -> CheckResult:
    """Verify that all files declared for removal no longer exist."""
    if not task.files_to_remove:
        return CheckResult(
            name="files_to_remove",
            status=CheckStatus.SKIP,
            detail="none declared",
        )
    removed = [
        f
        for f in task.files_to_remove
        if not (Path(f) if Path(f).is_absolute() else base_path / f).exists()
    ]
    all_removed = len(removed) == len(task.files_to_remove)
    return CheckResult(
        name="files_to_remove",
        status=CheckStatus.PASS if all_removed else CheckStatus.FAIL,
        detail=f"{len(removed)}/{len(task.files_to_remove)} removed",
    )
