"""Change promise checker — verifies task completion against declared promises."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

PROMISE_PATH = Path("docs/change_promise.toml")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class TaskCheckReport:
    task_index: int
    title: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def format(self) -> str:
        status = "PASS" if self.passed else "DISCREPANCY"
        failures = sum(1 for c in self.checks if not c.passed)
        lines = [f'TASK {self.task_index}: "{self.title}"']
        for c in self.checks:
            tag = "PASS" if c.passed else "FAIL"
            lines.append(f"  {c.name + ':':20s} {tag} ({c.detail})")
        suffix = (
            ""
            if self.passed
            else f" ({failures} failure{'s' if failures != 1 else ''})"
        )
        lines.append(f"  RESULT: {status}{suffix}")
        return "\n".join(lines)


def load_promise(path: Path = PROMISE_PATH) -> dict:
    return tomllib.loads(path.read_text())


def save_promise(data: dict, path: Path = PROMISE_PATH) -> None:
    path.write_bytes(tomli_w.dumps(data).encode())


def _git_diff_args(base_commit: str) -> list[str]:
    """Return the base git diff args against a specific commit."""
    return ["git", "diff", base_commit]


def _git_diff_names(base_commit: str) -> set[str]:
    """Return set of file paths changed since base_commit."""
    result = subprocess.run(
        [*_git_diff_args(base_commit), "--name-only"],
        capture_output=True,
        text=True,
    )
    names = set()
    for line in result.stdout.strip().splitlines():
        if line.strip():
            names.add(line.strip())
    return names


def _git_diff_numstat(base_commit: str) -> dict[str, tuple[int, int]]:
    """Return {filepath: (lines_added, lines_removed)} since base_commit."""
    stats: dict[str, tuple[int, int]] = {}
    result = subprocess.run(
        [*_git_diff_args(base_commit), "--numstat"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            added_str, removed_str, filepath = parts
            if added_str == "-" or removed_str == "-":
                continue  # binary file
            stats[filepath] = (int(added_str), int(removed_str))
    return stats


def _within_tolerance(expected: int, actual: int) -> bool:
    """Check if actual is within ±30% or ±30 lines of expected (whichever is greater)."""
    pct_tolerance = expected * 0.3
    abs_tolerance = 30
    tolerance = max(pct_tolerance, abs_tolerance)
    return abs(actual - expected) <= tolerance


def check_task(task_index: int, *, path: Path = PROMISE_PATH) -> TaskCheckReport:
    """Check a single task's promises against git reality."""
    data = load_promise(path)
    tasks = data.get("tasks", [])
    if task_index < 0 or task_index >= len(tasks):
        msg = f"Task index {task_index} out of range (0-{len(tasks) - 1})"
        raise IndexError(msg)

    base_commit = data.get("metadata", {}).get("base_commit", "HEAD")
    task = tasks[task_index]
    report = TaskCheckReport(task_index=task_index, title=task["title"])

    # Check files_to_create
    to_create = task.get("files_to_create", [])
    if to_create:
        existing = [f for f in to_create if Path(f).exists()]
        report.checks.append(
            CheckResult(
                name="files_to_create",
                passed=len(existing) == len(to_create),
                detail=f"{len(existing)}/{len(to_create)} exist",
            )
        )

    # Check files_to_modify
    to_modify = task.get("files_to_modify", [])
    if to_modify:
        diff_names = _git_diff_names(base_commit)
        modified = [f for f in to_modify if f in diff_names]
        report.checks.append(
            CheckResult(
                name="files_to_modify",
                passed=len(modified) == len(to_modify),
                detail=f"{len(modified)}/{len(to_modify)} modified",
            )
        )

    # Check files_to_remove
    to_remove = task.get("files_to_remove", [])
    if to_remove:
        removed = [f for f in to_remove if not Path(f).exists()]
        report.checks.append(
            CheckResult(
                name="files_to_remove",
                passed=len(removed) == len(to_remove),
                detail=f"{len(removed)}/{len(to_remove)} removed",
            )
        )

    # Check line counts
    expected_added = task.get("expected_lines_added", 0)
    expected_removed = task.get("expected_lines_removed", 0)
    all_files = set(to_create + to_modify)
    if all_files and (expected_added > 0 or expected_removed > 0):
        numstat = _git_diff_numstat(base_commit)
        actual_added = sum(numstat.get(f, (0, 0))[0] for f in all_files)
        actual_removed = sum(numstat.get(f, (0, 0))[1] for f in all_files)

        if expected_added > 0:
            added_ok = _within_tolerance(expected_added, actual_added)
            detail = f"expected ~{expected_added}, actual {actual_added}"
            if not added_ok:
                detail += " \u2014 outside \u00b130%/\u00b130 tolerance"
            report.checks.append(
                CheckResult(
                    name="lines_added",
                    passed=added_ok,
                    detail=detail,
                )
            )

        if expected_removed > 0:
            removed_ok = _within_tolerance(expected_removed, actual_removed)
            detail = f"expected ~{expected_removed}, actual {actual_removed}"
            if not removed_ok:
                detail += " \u2014 outside \u00b130%/\u00b130 tolerance"
            report.checks.append(
                CheckResult(
                    name="lines_removed",
                    passed=removed_ok,
                    detail=detail,
                )
            )

    return report


def complete_task(
    task_index: int, *, attempts: int = 1, path: Path = PROMISE_PATH
) -> None:
    """Mark a task as completed and record the number of attempts."""
    data = load_promise(path)
    tasks = data.get("tasks", [])
    if task_index < 0 or task_index >= len(tasks):
        msg = f"Task index {task_index} out of range (0-{len(tasks) - 1})"
        raise IndexError(msg)
    tasks[task_index]["completed"] = True
    tasks[task_index]["attempts"] = attempts
    save_promise(data, path)


def status(path: Path = PROMISE_PATH) -> str:
    """Return a formatted status of all tasks."""
    data = load_promise(path)
    tasks = data.get("tasks", [])
    lines = []
    for i, task in enumerate(tasks):
        mark = "\u2713" if task.get("completed") else "\u2717"
        lines.append(f"  [{mark}] {i}: {task['title']}")
    done = sum(1 for t in tasks if t.get("completed"))
    lines.append(f"\n  {done}/{len(tasks)} completed")
    return "\n".join(lines)


def plan(path: Path = PROMISE_PATH) -> str:
    """Return a formatted plan view of all tasks for human review."""
    data = load_promise(path)
    metadata = data.get("metadata", {})
    tasks = data.get("tasks", [])

    base = metadata.get("base_commit", "unknown")
    task_word = "task" if len(tasks) == 1 else "tasks"
    lines = [f"PLAN: {len(tasks)} {task_word} (base: {base})", ""]

    for i, task in enumerate(tasks):
        lines.append(f"Task {i}: {task['title']}")
        if goal := task.get("goal"):
            lines.append(f"  Goal:   {goal}")

        to_create = task.get("files_to_create", [])
        if to_create:
            lines.append(f"  Create: {', '.join(to_create)}")

        to_modify = task.get("files_to_modify", [])
        if to_modify:
            lines.append(f"  Modify: {', '.join(to_modify)}")

        to_remove = task.get("files_to_remove", [])
        if to_remove:
            lines.append(f"  Remove: {', '.join(to_remove)}")

        context = task.get("context_files", [])
        if context:
            lines.append(f"  Reads:  {', '.join(context)}")

        skills = task.get("reference_skills", [])
        if skills:
            lines.append(f"  Skills: {', '.join(skills)}")

        docs = task.get("doc_sections", [])
        if docs:
            lines.append(f"  Docs:   {', '.join(docs)}")

        deps = task.get("dependencies", [])
        if deps:
            dep_labels = [f"Task {d}" for d in deps]
            lines.append(f"  Deps:   {', '.join(dep_labels)}")
        else:
            lines.append("  Deps:   none")

        added = task.get("expected_lines_added", 0)
        removed = task.get("expected_lines_removed", 0)
        lines.append(f"  Lines:  +{added} / -{removed}")
        lines.append("")

    return "\n".join(lines)


def cleanup(path: Path = PROMISE_PATH) -> None:
    """Remove the promise file after all tasks are complete."""
    path.unlink()


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(
            "Usage: python -m prothon.promise <check|status|complete|plan|cleanup> [task-index]"
        )
        sys.exit(1)

    command = args[0]

    if not PROMISE_PATH.exists() and command in (
        "status",
        "check",
        "complete",
        "plan",
        "cleanup",
    ):
        print(f"No promise file found at {PROMISE_PATH}")
        sys.exit(1)

    if command == "status":
        print(status())

    elif command == "plan":
        print(plan())

    elif command == "check":
        if len(args) < 2:
            print("Usage: python -m prothon.promise check <task-index>")
            sys.exit(1)
        try:
            idx = int(args[1])
        except ValueError:
            print(f"Error: task-index must be an integer, got '{args[1]}'")
            sys.exit(1)
        report = check_task(idx)
        print(report.format())
        sys.exit(0 if report.passed else 1)

    elif command == "complete":
        if len(args) < 2:
            print("Usage: python -m prothon.promise complete <task-index> [attempts]")
            sys.exit(1)
        try:
            idx = int(args[1])
        except ValueError:
            print(f"Error: task-index must be an integer, got '{args[1]}'")
            sys.exit(1)
        attempts = 1
        if len(args) >= 3:
            try:
                attempts = int(args[2])
            except ValueError:
                print(f"Error: attempts must be an integer, got '{args[2]}'")
                sys.exit(1)
        complete_task(idx, attempts=attempts)
        print(
            f"Task {idx} marked as completed ({attempts} attempt{'s' if attempts != 1 else ''})."
        )

    elif command == "cleanup":
        cleanup()
        print("Promise file removed.")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
