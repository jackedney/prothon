# Execute/Planning/Promise Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rework `promise.py` for base-commit-aware diffing and enriched format, rewrite the execute skill for the plan+loop architecture, remove senior-dev skill.

**Architecture:** Enriched `change_promise.toml` replaces both the old promise and `PLAN.md`. Self-correcting task loops replace the senior-dev reviewer. All git diffs are against a stored base commit SHA.

**Tech Stack:** Python 3.11+, tomllib/tomli-w, subprocess (git), pytest

---

### Task 1: Tighten tolerance from ±50%/±50 to ±30%/±30

**Files:**
- Modify: `src/prothon/promise.py:96-101`
- Create: `tests/test_promise.py`

**Step 1: Write the failing test**

```python
# tests/test_promise.py
"""Tests for the change promise checker."""

from prothon.promise import _within_tolerance


class TestWithinTolerance:
    """Tests for _within_tolerance with ±30%/±30 tolerance."""

    def test_exact_match(self):
        assert _within_tolerance(100, 100) is True

    def test_at_thirty_percent_upper(self):
        # 100 + 30% = 130
        assert _within_tolerance(100, 130) is True

    def test_over_thirty_percent_upper(self):
        assert _within_tolerance(100, 131) is False

    def test_at_thirty_percent_lower(self):
        # 100 - 30% = 70
        assert _within_tolerance(100, 70) is True

    def test_under_thirty_percent_lower(self):
        assert _within_tolerance(100, 69) is False

    def test_absolute_floor_when_small_expected(self):
        # 10 expected, 30% = 3, but absolute minimum is 30
        # So tolerance is 30: range is -20 to 40
        assert _within_tolerance(10, 40) is True
        assert _within_tolerance(10, 41) is False

    def test_zero_expected_uses_absolute(self):
        # 0 expected, 30% = 0, absolute = 30
        assert _within_tolerance(0, 30) is True
        assert _within_tolerance(0, 31) is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_promise.py::TestWithinTolerance -v`
Expected: FAIL — `test_over_thirty_percent_upper` passes when it shouldn't (old tolerance is ±50%/±50)

**Step 3: Write minimal implementation**

In `src/prothon/promise.py`, change `_within_tolerance`:

```python
def _within_tolerance(expected: int, actual: int) -> bool:
    """Check if actual is within ±30% or ±30 lines of expected (whichever is greater)."""
    pct_tolerance = expected * 0.3
    abs_tolerance = 30
    tolerance = max(pct_tolerance, abs_tolerance)
    return abs(actual - expected) <= tolerance
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_promise.py::TestWithinTolerance -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add tests/test_promise.py src/prothon/promise.py
git commit -m "fix: tighten promise tolerance from ±50%/±50 to ±30%/±30"
```

---

### Task 2: Base-commit-aware git diffing

**Files:**
- Modify: `src/prothon/promise.py:53-93` (git functions) and `src/prothon/promise.py:104-177` (check_task)
- Modify: `tests/test_promise.py`

**Step 1: Write the failing tests**

Append to `tests/test_promise.py`:

```python
from unittest.mock import patch, MagicMock
from prothon.promise import (
    _git_diff_args,
    _git_diff_names,
    _git_diff_numstat,
    check_task,
    load_promise,
    save_promise,
)
import tomli_w


class TestGitDiffArgs:
    """Tests for base-commit-aware _git_diff_args."""

    def test_uses_base_commit(self):
        result = _git_diff_args("abc1234")
        assert result == ["git", "diff", "abc1234"]

    def test_different_commit(self):
        result = _git_diff_args("def5678")
        assert result == ["git", "diff", "def5678"]


class TestGitDiffNames:
    """Tests for _git_diff_names with base_commit parameter."""

    @patch("prothon.promise.subprocess.run")
    def test_returns_modified_files(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="src/app.py\nsrc/auth.py\n",
        )
        result = _git_diff_names("abc1234")
        assert result == {"src/app.py", "src/auth.py"}
        mock_run.assert_called_once_with(
            ["git", "diff", "abc1234", "--name-only"],
            capture_output=True,
            text=True,
        )


class TestGitDiffNumstat:
    """Tests for _git_diff_numstat with base_commit parameter."""

    @patch("prothon.promise.subprocess.run")
    def test_parses_numstat(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="50\t10\tsrc/app.py\n70\t0\tsrc/auth.py\n",
        )
        result = _git_diff_numstat("abc1234")
        assert result == {
            "src/app.py": (50, 10),
            "src/auth.py": (70, 0),
        }
        mock_run.assert_called_once_with(
            ["git", "diff", "abc1234", "--numstat"],
            capture_output=True,
            text=True,
        )


class TestCheckTaskReadsBaseCommit:
    """Tests that check_task reads base_commit from promise metadata."""

    @patch("prothon.promise._git_diff_numstat")
    @patch("prothon.promise._git_diff_names")
    def test_passes_base_commit_to_git_functions(
        self, mock_names, mock_numstat, tmp_path
    ):
        mock_names.return_value = {"src/app.py"}
        mock_numstat.return_value = {"src/app.py": (50, 5)}

        promise_path = tmp_path / "promise.toml"
        data = {
            "metadata": {"base_commit": "abc1234"},
            "tasks": [
                {
                    "title": "Test task",
                    "files_to_create": [],
                    "files_to_modify": ["src/app.py"],
                    "files_to_remove": [],
                    "expected_lines_added": 50,
                    "expected_lines_removed": 5,
                    "completed": False,
                }
            ],
        }
        save_promise(data, promise_path)

        check_task(0, path=promise_path)

        mock_names.assert_called_once_with("abc1234")
        mock_numstat.assert_called_once_with("abc1234")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_promise.py -k "GitDiff or CheckTaskReads" -v`
Expected: FAIL — current functions don't accept `base_commit` parameter

**Step 3: Implement base-commit-aware diffing**

Replace the three git functions and update `check_task` in `src/prothon/promise.py`:

```python
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
```

In `check_task`, read `base_commit` from metadata and pass it through:

```python
def check_task(task_index: int, path: Path = PROMISE_PATH) -> TaskCheckReport:
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
        report.checks.append(CheckResult(
            name="files_to_create",
            passed=len(existing) == len(to_create),
            detail=f"{len(existing)}/{len(to_create)} exist",
        ))

    # Check files_to_modify
    to_modify = task.get("files_to_modify", [])
    if to_modify:
        diff_names = _git_diff_names(base_commit)
        modified = [f for f in to_modify if f in diff_names]
        report.checks.append(CheckResult(
            name="files_to_modify",
            passed=len(modified) == len(to_modify),
            detail=f"{len(modified)}/{len(to_modify)} modified",
        ))

    # Check files_to_remove
    to_remove = task.get("files_to_remove", [])
    if to_remove:
        removed = [f for f in to_remove if not Path(f).exists()]
        report.checks.append(CheckResult(
            name="files_to_remove",
            passed=len(removed) == len(to_remove),
            detail=f"{len(removed)}/{len(to_remove)} removed",
        ))

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
                detail += " — outside ±30%/±30 tolerance"
            report.checks.append(CheckResult(
                name="lines_added",
                passed=added_ok,
                detail=detail,
            ))

        if expected_removed > 0:
            removed_ok = _within_tolerance(expected_removed, actual_removed)
            detail = f"expected ~{expected_removed}, actual {actual_removed}"
            if not removed_ok:
                detail += " — outside ±30%/±30 tolerance"
            report.checks.append(CheckResult(
                name="lines_removed",
                passed=removed_ok,
                detail=detail,
            ))

    return report
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_promise.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/prothon/promise.py tests/test_promise.py
git commit -m "feat: base-commit-aware diffing in promise checker"
```

---

### Task 3: Add `plan` pretty-print command

**Files:**
- Modify: `src/prothon/promise.py` (add `plan` function + CLI handler)
- Modify: `tests/test_promise.py`

**Step 1: Write the failing test**

Append to `tests/test_promise.py`:

```python
from prothon.promise import plan


class TestPlan:
    """Tests for plan pretty-print function."""

    def test_formats_single_task(self, tmp_path):
        data = {
            "metadata": {"base_commit": "abc1234", "created_at": "2026-02-18T14:30:00"},
            "tasks": [
                {
                    "title": "Add auth middleware",
                    "goal": "JWT validation on all protected routes",
                    "success_criteria": "401 without token",
                    "files_to_create": ["src/auth.py", "tests/test_auth.py"],
                    "files_to_modify": ["src/app.py"],
                    "files_to_remove": [],
                    "context_files": ["src/middleware.py"],
                    "doc_sections": ["DESIGN.md#Auth"],
                    "reference_skills": ["tech-fastapi"],
                    "dependencies": [],
                    "expected_lines_added": 120,
                    "expected_lines_removed": 5,
                    "completed": False,
                    "attempts": 0,
                }
            ],
        }
        p = tmp_path / "promise.toml"
        save_promise(data, p)

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

    def test_formats_dependencies(self, tmp_path):
        data = {
            "metadata": {"base_commit": "abc1234"},
            "tasks": [
                {
                    "title": "Task A",
                    "goal": "First",
                    "files_to_create": [],
                    "files_to_modify": [],
                    "files_to_remove": [],
                    "dependencies": [],
                    "expected_lines_added": 10,
                    "expected_lines_removed": 0,
                    "completed": False,
                    "attempts": 0,
                },
                {
                    "title": "Task B",
                    "goal": "Second",
                    "files_to_create": [],
                    "files_to_modify": [],
                    "files_to_remove": [],
                    "dependencies": [0],
                    "expected_lines_added": 20,
                    "expected_lines_removed": 0,
                    "completed": False,
                    "attempts": 0,
                },
            ],
        }
        p = tmp_path / "promise.toml"
        save_promise(data, p)

        output = plan(p)
        assert "PLAN: 2 tasks" in output
        assert "Task 0" in output
        assert "Task 1" in output
        assert "Deps:   Task 0" in output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_promise.py::TestPlan -v`
Expected: FAIL — `plan` function doesn't exist yet

**Step 3: Implement the plan function and CLI handler**

Add to `src/prothon/promise.py`:

```python
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
```

Add the `plan` CLI handler in the `main()` function, between the `status` and `check` handlers:

```python
    elif command == "plan":
        print(plan())
```

Also update the usage string:

```python
        print("Usage: python -m prothon.promise <check|status|complete|plan> [task-index]")
```

And the file-existence guard:

```python
    if not PROMISE_PATH.exists() and command in ("status", "check", "complete", "plan"):
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_promise.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/prothon/promise.py tests/test_promise.py
git commit -m "feat: add 'plan' pretty-print command to promise CLI"
```

---

### Task 4: Add attempts tracking to complete_task

**Files:**
- Modify: `src/prothon/promise.py:180-188` (complete_task)
- Modify: `tests/test_promise.py`

**Step 1: Write the failing test**

Append to `tests/test_promise.py`:

```python
import tomllib
from prothon.promise import complete_task


class TestCompleteTask:
    """Tests for complete_task with attempts tracking."""

    def test_marks_complete_and_records_attempts(self, tmp_path):
        data = {
            "metadata": {"base_commit": "abc1234"},
            "tasks": [
                {"title": "Test", "completed": False, "attempts": 0}
            ],
        }
        p = tmp_path / "promise.toml"
        save_promise(data, p)

        complete_task(0, attempts=3, path=p)

        result = tomllib.loads(p.read_text())
        assert result["tasks"][0]["completed"] is True
        assert result["tasks"][0]["attempts"] == 3

    def test_defaults_to_one_attempt(self, tmp_path):
        data = {
            "metadata": {"base_commit": "abc1234"},
            "tasks": [
                {"title": "Test", "completed": False, "attempts": 0}
            ],
        }
        p = tmp_path / "promise.toml"
        save_promise(data, p)

        complete_task(0, path=p)

        result = tomllib.loads(p.read_text())
        assert result["tasks"][0]["attempts"] == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_promise.py::TestCompleteTask -v`
Expected: FAIL — `complete_task` doesn't accept `attempts` parameter

**Step 3: Implement attempts tracking**

Replace `complete_task` in `src/prothon/promise.py`:

```python
def complete_task(task_index: int, *, attempts: int = 1, path: Path = PROMISE_PATH) -> None:
    """Mark a task as completed and record the number of attempts."""
    data = load_promise(path)
    tasks = data.get("tasks", [])
    if task_index < 0 or task_index >= len(tasks):
        msg = f"Task index {task_index} out of range (0-{len(tasks) - 1})"
        raise IndexError(msg)
    tasks[task_index]["completed"] = True
    tasks[task_index]["attempts"] = attempts
    save_promise(data, path)
```

Update the CLI handler to accept an optional `--attempts` argument:

```python
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
        print(f"Task {idx} marked as completed ({attempts} attempt{'s' if attempts != 1 else ''}).")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_promise.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/prothon/promise.py tests/test_promise.py
git commit -m "feat: track attempt count when completing promise tasks"
```

---

### Task 5: Rewrite execute SKILL.md

**Files:**
- Modify: `.agents/skills/execute/SKILL.md` (full rewrite)

**Step 1: Write the new execute skill**

Replace the entire contents of `.agents/skills/execute/SKILL.md` with the new plan+loop architecture:

- Phase 1: Plan — read docs, scan code, generate enriched `docs/change_promise.toml`, run `python -m prothon.promise plan`, get user approval
- Phase 2: Execute — for each task (respecting dependencies), launch a fresh subagent with the self-correcting loop: implement → `poe check` → `git add` + `git commit` → `python -m prothon.promise check <idx>` → if fail, fix and retry (max 3) → `python -m prothon.promise complete <idx>`
- Phase 3: Verify — launch compliance-checker subagent

Key content for the new skill:
- Remove small/large path split — everything goes through plan + task loops
- Remove all references to `docs/PLAN.md` — replaced by enriched promise
- Remove all references to senior-dev skill — replaced by self-correcting loop
- Include the enriched TOML schema as a reference
- Include the exact subagent prompt template
- Include the guards section (don't modify docs, don't skip plan, don't run parallel tasks on same files)

**Step 2: Verify the skill file is valid**

Read it back and confirm frontmatter is valid YAML, content is well-structured markdown.

**Step 3: Commit**

```bash
git add .agents/skills/execute/SKILL.md
git commit -m "feat: rewrite execute skill with plan+loop architecture"
```

---

### Task 6: Delete senior-dev skill

**Files:**
- Delete: `.agents/skills/senior-dev/SKILL.md`

**Step 1: Delete the file**

```bash
rm .agents/skills/senior-dev/SKILL.md
rmdir .agents/skills/senior-dev
```

**Step 2: Verify no remaining references**

Search the codebase for "senior-dev" — should find no references in active code (only in git history and the design doc).

Run: `grep -r "senior-dev" .agents/ src/ tests/`
Expected: No output (no remaining references)

**Step 3: Commit**

```bash
git add -A .agents/skills/senior-dev/
git commit -m "chore: remove senior-dev skill (absorbed into task loop)"
```

---

### Task 7: Run full quality checks

**Step 1: Run all checks**

Run: `uv run pytest tests/test_promise.py -v`
Expected: All tests PASS

Run: `uv run ruff check src/ tests/`
Expected: No errors

Run: `uv run ruff format --check src/ tests/`
Expected: No reformatting needed

**Step 2: Fix any issues found**

If any quality check fails, fix the issues and re-run.

**Step 3: Final commit (if needed)**

```bash
git add -A
git commit -m "fix: address quality check findings"
```
