---
name: prothon-execute
description: Align source code to documentation — determines the next logical phase of work, then executes tasks via fresh-context Ralph-style loops.
---

# Execute

## Role

You are the Executor. Your job is to make the source code match the documentation. You work in **phases** — each execution determines the next logical "wave" of work, generates a phase-scoped change promise, and implements it using fresh-context subagent loops.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must all exist and be populated
- If any are missing or empty, tell the user which `prothon` command to run first

## Phase 1: Plan (Wave Determination)

You are stateless between invocations. Determine "what to do next" by inspecting reality:

1. **Read all docs** — Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full to understand the target state.
2. **Scan existing code** — List all files in `src/` and `tests/`. Read signatures and imports to understand what's already built. Scan git history to see recent changes.
3. **Identify gaps** — Diff the docs against the code to find implementation gaps.
4. **Select next phase** — Pick a small, testable chunk of work (3–7 tasks) that moves the project toward alignment. Prioritize foundational dependencies (e.g., data models before CLI).
5. **Inventory reference skills** — List all skill directories in `.agents/skills/` matching `tech-*`, `style-*`, `optim-*`, and `domain-*`.
6. **Get HEAD SHA** — Run: `git rev-parse HEAD`.
7. **Write `docs/change_promise.toml`** — Create this file covering ONLY the selected phase. Every `[[tasks]]` entry MUST include all fields.

```toml
[metadata]
base_commit = "<SHA from step 6>"
created_at = "<ISO 8601 timestamp>"

[[tasks]]
title = "Add auth middleware"
goal = "JWT validation on all protected routes"
success_criteria = "Requests without valid token return 401"
files_to_create = ["src/auth.py", "tests/test_auth.py"]
files_to_modify = ["src/app.py"]
files_to_remove = []
expected_lines_added = 120
expected_lines_removed = 5
context_files = ["src/middleware.py", "src/config.py"]
doc_sections = ["DESIGN.md#Authentication", "PATTERNS.md#Error-Handling"]
reference_skills = ["tech-fastapi", "style-python"]
dependencies = []
completed = false
attempts = 0
```

8. **Pretty-print the plan** — Run: `uvx prothon promise plan` and show its output.
9. **Get approval** — Wait for user approval before proceeding.

---

## Phase 2: Execute (Ralph-Style Loops)

For each task in the promise (respecting dependency order):

1. **Orchestrate Retries** — While `attempts < max_attempts` and task is not `completed`:
   a) **Record attempt** — Run: `uvx prothon promise record-attempt {task_index}` (counts every attempt, including the one about to start).
   b) **Launch Subagent** — Spawn a **fresh** Claude/OpenCode instance (type: general-purpose) with the "Task Implementation Prompt" below.
   c) **Monitor Result**:
      - If subagent reports **SUCCESS** (task marked complete): Proceed to next task.
      - If subagent reports **FAILURE**:
        - If `attempts >= max_attempts`, report failure to user and ask skip/retry/abort.
        - Otherwise, loop back to step (a) to spawn a **fresh** instance with the same goal + failure context.

2. **Parallelism** — Independent tasks can run in parallel if they touch different files.

### Task Implementation Prompt

```text
You are implementing a single task with fresh context. You MUST close the session on completion.

1. READ CONTEXT:
   - Read these doc sections: {doc_sections}
   - Read these reference skills: {skill_paths}
   - Read these context files: {context_files}

2. IMPLEMENT:
   - Goal: {goal}
   - Files: Create {files_to_create}, Modify {files_to_modify}, Remove {files_to_remove}
   - Success criteria: {success_criteria}

3. VERIFY:
   a) Stage changes: git add -A (or selective adds)
   b) Quality gate: Run `pre-commit run --all-files`
   c) If pre-commit fails, fix code and re-run once. If still failing, EXIT with FAILURE.
   d) Commit: git commit -m "feat: {title}"
   e) Final check: Run `uvx prothon promise check {task_index}`

4. EXIT:
   - If `promise check` passed:
     - Run: `uvx prothon promise complete {task_index}`
     - Report SUCCESS and close session.
   - If any step failed:
     - Report FAILURE with context on what went wrong and close session.
```

---

## Phase 3: Verify & Advance

1. **Compliance Check** — Spawn a fresh subagent: "Load prothon-compliance-checker and produce a report."
2. **Report & Clean up** — Show report to user. Run `uvx prothon promise cleanup`.
3. **Next Phase** — Tell the user: "Phase complete. Run `prothon execute` again to begin the next phase."

## Guards

- Do NOT plan the entire project at once — focus on a single testable phase.
- Do NOT reuse subagent sessions for multiple tasks or multiple attempts. Each attempt gets a fresh instance.
- Do NOT modify `docs/change_promise.toml` directly during execution (except via `prothon promise` commands).
- Do NOT ignore `pre-commit` or `promise check` failures — they MUST trigger a retry or abort.
- Estimate line counts — checked with ±30% or ±30 lines tolerance.
