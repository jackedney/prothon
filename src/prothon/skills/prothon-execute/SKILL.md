---
name: prothon-execute
description: "[What] Align source code to documentation. [When] Use to implement features or fixes based on the doc hierarchy. [Capabilities] Wave-based phase planning, subagent-driven development loops with two-stage review, and automated verification."
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
7. **Write `docs/change_promise.toml` (Writing Plans)** — Create this file covering ONLY the selected phase. Break work into bite-sized tasks (2-5 minutes of work each).
   - Document exactly which files to touch for each task.
   - Embed complete code concepts or context rather than vague descriptions ("add validation").
   - DRY. YAGNI. TDD. Every `[[tasks]]` entry MUST include all fields.

```toml
[metadata]
base_commit = "<SHA from step 6>"
created_at = "<ISO 8601 timestamp>"

[[tasks]]
title = "Add auth middleware"
goal = "Implement JWT validation on all protected routes. Write failing test, implement minimal code to pass, commit."
success_criteria = "pytest tests/test_auth.py passes and requests without valid token return 401"
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

## Phase 2: Execute (Subagent-Driven Development)

For each task in the promise (respecting dependency order):

1. **Orchestrate Retries & Two-Stage Review** — While `attempts < max_attempts` and task is not `completed`:
   a) **Record attempt** — Run: `uvx prothon promise record-attempt {task_index}` (counts every attempt, including the one about to start).
   b) **Launch Implementer Subagent** — Spawn a **fresh** Claude/OpenCode instance (type: general-purpose) using `./implementer-prompt.md`. Keep this session alive until both reviewers approve. If it asks questions before implementing, answer them.
   c) **Launch Spec Reviewer Subagent** — Once the implementer finishes, spawn a **fresh** instance using `./spec-reviewer-prompt.md` to confirm the code matches the specification.
      - If it reports gaps/issues, send the feedback to the **still-open Implementer Subagent** to fix. Re-launch a fresh spec reviewer until approved.
   d) **Launch Code Quality Reviewer Subagent** — Once spec compliance is approved, spawn a **fresh** instance using `./code-quality-reviewer-prompt.md`.
      - If it reports issues, send the feedback to the **still-open Implementer Subagent** to fix. Re-launch a fresh code quality reviewer until approved.
   Once both reviewers approve, the implementer session closes.
   e) **Monitor Result**:
      - If all reviewers approve and verifications pass (task marked complete): Proceed to next task.
      - If the process fails and `attempts >= max_attempts`: report failure to user and ask skip/retry/abort.
      - Otherwise, loop back to step (a) to start a new attempt.

2. **Parallelism** — Independent tasks can run in parallel if they touch different files.

*(The prompts `implementer-prompt.md`, `spec-reviewer-prompt.md`, and `code-quality-reviewer-prompt.md` are located in this skill directory.)*

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
