---
name: prothon-execute
description: "[What] Align source code to documentation. [When] Use to implement features or fixes based on the doc hierarchy. [Capabilities] Wave-based phase planning, self-correcting Ralph-style execution loops, and automated verification."
---

# Execute

## Role

You are the Executor. Align source code to documentation by determining the next logical phase of work, generating a phase-scoped change promise, and implementing it via fresh-context subagent loops.

## Critical

- **Plan first.** Never skip the approval of `docs/change_promise.toml`.
- **Phase-scoped.** Plan one small testable phase (3-7 tasks), not the entire project.
- **Lean context.** Reference file paths in prompts; do NOT paste full contents.
- **Selective staging.** Stage only task-related files by explicit path (`git add <file>`). Do NOT use `git add -u` or `git add -A` as they stage all tracked changes repo-wide.
- **Fresh instances.** Never reuse subagent sessions for multiple tasks or attempts.
- **No parallel conflicts.** Never launch subagents that touch the same files simultaneously.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must be populated.

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

1. LOAD CONTEXT:
   - Read these doc sections: {doc_sections}
   - Activate these reference skills: {skill_names}
   - Read these context files: {context_files}

2. IMPLEMENT:
   - Goal: {goal}
   - Files: Create {files_to_create}, Modify {files_to_modify}, Remove {files_to_remove}
   - Success criteria: {success_criteria}

3. VERIFY:
   a) Stage selectively by explicit path:
      - Stage modified files: git add {files_to_modify}
      - Stage new files: git add {files_to_create}
      - Remove deleted files: git rm {files_to_remove}
   b) Type checking: Run `uvx ty check src/ tests/` and fix ALL errors and warnings before proceeding. ty errors are NOT optional — they indicate real type safety issues that must be resolved. Do not suppress warnings or skip this step.
   c) Quality gate: Run `pre-commit run --all-files --show-diff-on-failure`
   d) If hooks auto-fixed files, re-stage the specific files and re-run pre-commit once. If still failing, EXIT with FAILURE.
   e) Commit: git commit -m "feat: {title}"
   f) Final check: Run `uvx prothon promise check {task_index}`

4. EXIT:
   - If `promise check` passed:
     - Run: `uvx prothon promise complete {task_index}`
     - Report SUCCESS and close session.
   - If any step failed:
     - Report FAILURE with context on what went wrong and close session.
```

---

## Phase 3: Verify & Advance

1. **Compliance Check** — Spawn a fresh subagent: "Activate prothon-compliance-checker and produce a report."
2. **Report & Clean up** — Show report to user. Run `uvx prothon promise cleanup`.
3. **Next Phase** — Tell the user: "Phase complete. Run `prothon execute` again to begin the next phase."

## Guards

- **TOML only.** The plan is ALWAYS `docs/change_promise.toml`. No markdown plans.
- **No manual tables.** Use `uvx prothon promise plan` output only.
- **Doc integrity.** Do NOT modify SPEC, DESIGN, or PATTERNS.
- **Fresh context.** Each attempt gets a fresh subagent instance.
- **Phase-scoped.** Focus on a single testable phase, not the entire project.
- **No bypassing.** Do NOT ignore `pre-commit` or `promise check` failures — they MUST trigger a retry or abort.
- **Line estimates.** Checked with ±30% or ±30 lines tolerance.
