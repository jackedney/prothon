# Execute, Planning & Promise Redesign

**Goal:** Replace the current monolithic execute skill, separate PLAN.md, and buggy promise system with a streamlined plan-then-loop architecture where the promise TOML is the single source of truth for both planning and verification.

**Architecture:** Plan phase generates an enriched `docs/change_promise.toml` (upfront contract with context-routing fields). Execute phase launches one fresh-context subagent per task in a self-correcting loop: implement, check (promise + quality gates), fix if needed, repeat until pass.

---

## Architecture Overview

### Components

1. **Planner** (execute skill, phase 1) — Reads docs, scans code, generates enriched `docs/change_promise.toml`, presents to user for approval.
2. **Task Loop** (subagent per task) — Fresh-context agent that receives one task. Implements → checks → fixes if needed → loops until pass or max retries (3).
3. **Promise CLI** (`python -m prothon.promise`) — Enhanced with base-commit-aware diffing, `plan` command for human-readable review, tighter tolerance.

### Flow

```
prothon execute
  │
  ├─ Phase 1: Plan
  │   ├─ Read SPEC.md, DESIGN.md, PATTERNS.md
  │   ├─ Inventory reference skills (tech-*, style-*, optim-*, domain-*)
  │   ├─ Scan code structure (signatures + imports only)
  │   ├─ Identify gaps between docs and code
  │   ├─ Generate docs/change_promise.toml (base_commit = HEAD)
  │   ├─ Run: python -m prothon.promise plan (pretty-print for review)
  │   └─ Ask user for approval
  │
  └─ Phase 2: Execute (per task, respecting dependencies)
      ├─ For each task:
      │   └─ Launch subagent with self-correcting loop:
      │       ┌─ Read context (doc sections, skills, context files)
      │       ├─ Implement (create/modify/remove files)
      │       ├─ Check: poe check + promise check
      │       ├─ Pass? → git add + commit → promise complete
      │       └─ Fail? → fix → retry (max 3)
      │
      ├─ After each task: check success or surface failure to user
      ├─ Independent tasks can run in parallel
      └─ Final: compliance-checker subagent
```

---

## Enriched Promise Format

`docs/change_promise.toml` replaces both the old promise format and `docs/PLAN.md`:

```toml
[metadata]
base_commit = "abc1234"               # SHA of HEAD when plan was generated
created_at = "2026-02-18T14:30:00"

[[tasks]]
title = "Add auth middleware"
goal = "JWT validation on all protected routes"
success_criteria = "Requests without valid token return 401"

# File contract (verifiable)
files_to_create = ["src/auth.py", "tests/test_auth.py"]
files_to_modify = ["src/app.py"]
files_to_remove = []
expected_lines_added = 120
expected_lines_removed = 5

# Context routing (tells subagent what to read)
context_files = ["src/middleware.py", "src/config.py"]
doc_sections = ["DESIGN.md#Authentication", "PATTERNS.md#Error-Handling"]
reference_skills = ["tech-fastapi", "style-python"]

# Execution state
dependencies = []     # indices of tasks that must complete first
completed = false
attempts = 0          # loop iterations taken
```

### Changes from current format

- `base_commit` in metadata — all diffs use `git diff <base_commit>` instead of `git diff HEAD`
- `goal`, `context_files`, `doc_sections`, `reference_skills` — replaces PLAN.md
- `dependencies` — task ordering
- `attempts` — tracks loop iterations
- `created_at` — provenance
- Tolerance tightened: ±30% or ±30 lines (whichever greater)

---

## Task Loop (Subagent Prompt)

Each task subagent receives this structured prompt:

```
You are implementing a single task. Follow this loop:

1. READ CONTEXT:
   - Read these doc sections: {doc_sections}
   - Read these reference skills: {skill paths}
   - Read these context files: {context_files}

2. IMPLEMENT:
   - Goal: {goal}
   - Files to create: {files_to_create}
   - Files to modify: {files_to_modify}
   - Files to remove: {files_to_remove}
   - Success criteria: {success_criteria}

3. CHECK:
   a) Run: poe check
   b) Stage files: git add {all task files}
   c) Commit: git commit -m "feat: {title}"
   d) Run: python -m prothon.promise check {task_index}

4. IF ANY CHECK FAILS:
   - Read the error output
   - Fix the issues
   - Go to step 3 (max 3 total attempts)

5. IF ALL PASS:
   - Run: python -m prothon.promise complete {task_index}
   - Report success
```

### Design decisions

- **Subagent commits before promise check** — `git diff <base_commit>` sees committed changes
- **`poe check` runs full suite** — ruff, ty, bandit, vulture, complexipy, tests
- **Max 3 retries** — after 3 failures, surface error to orchestrator
- **Independent tasks can run in parallel** — but no two tasks touching the same files
- **No senior-dev reviewer** — the loop IS the review

---

## Promise CLI Changes

### Commands

| Command | Behavior |
|---|---|
| `promise plan` | **New.** Pretty-prints all tasks for human review |
| `promise check <idx>` | Uses `git diff <base_commit>`. Tighter ±30%/±30 tolerance |
| `promise complete <idx>` | Marks complete, records attempt count |
| `promise status` | Shows completion progress (unchanged) |

### `promise plan` output

```
PLAN: 3 tasks (base: abc1234)

Task 0: Add auth middleware
  Goal:   JWT validation on all protected routes
  Create: src/auth.py, tests/test_auth.py
  Modify: src/app.py
  Reads:  src/middleware.py, src/config.py
  Skills: tech-fastapi, style-python
  Docs:   DESIGN.md#Authentication, PATTERNS.md#Error-Handling
  Deps:   none
  Lines:  +120 / -5

Task 1: Add config loading
  ...
```

### Base-commit-aware diffing

```python
def _git_diff_args(base_commit: str) -> list[str]:
    return ["git", "diff", base_commit]
```

Solves the core bug: new files committed by earlier tasks show up in diff. Each subagent commits before check, so all changes are visible.

---

## Execute Skill Rewrite

### Phase 1: Plan (orchestrator, direct)

1. Read all docs (SPEC.md, DESIGN.md, PATTERNS.md)
2. Inventory reference skills (tech-*, style-*, optim-*, domain-*)
3. Scan code structure (signatures + imports, not full bodies)
4. Identify gaps between docs and code
5. Generate `docs/change_promise.toml` with all tasks, `base_commit = HEAD`
6. Run `python -m prothon.promise plan` to pretty-print
7. Ask user for approval — do not proceed until approved

### Phase 2: Execute (orchestrator launches subagents)

1. For each task (respecting dependency order):
   - Wait for all `dependencies` to be complete
   - Launch fresh subagent with task loop prompt
   - Independent tasks can run in parallel
2. After each subagent returns:
   - If succeeded (task marked complete): continue
   - If failed (3 retries exhausted): report to user, ask skip/retry/abort
3. Run `python -m prothon.promise status` to confirm all complete

### Phase 3: Verify

1. Launch compliance-checker subagent
2. Report results to user

### Removed

- Small/large path split — everything goes through plan + loop
- Senior-dev skill — absorbed into self-correcting loop
- References to `docs/PLAN.md` — replaced by enriched promise

---

## File Changes

### Modify

| File | Change |
|---|---|
| `src/prothon/promise.py` | Base-commit diffing, `plan` command, tighter tolerance, `attempts` field |
| `.agents/skills/execute/SKILL.md` | Full rewrite per above |

### Delete

| File | Reason |
|---|---|
| `.agents/skills/senior-dev/SKILL.md` | Absorbed into task loop |

### Unchanged

| File | Why |
|---|---|
| `src/prothon/cli.py` | Already correct |
| All other skills | Independent, no changes needed |
| SPEC.md, DESIGN.md, PATTERNS.md | Not part of execute system |
