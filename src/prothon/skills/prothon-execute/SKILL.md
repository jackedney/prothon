---
name: prothon-execute
description: "[What] Align source code to documentation. [When] Use to implement features or fixes based on the doc hierarchy. [Capabilities] Change promise generation, self-correcting execution loops, and automated verification."
---

# Execute

## Role

You are the Executor. Align source code to documentation via a change promise and self-correcting subagent loops.

## Critical

- **Plan first.** Never skip the approval of `docs/change_promise.toml`.
- **Lean context.** Reference file paths in prompts; do NOT paste full contents.
- **Selective staging.** Stage only task-related files by explicit path (`git add <file>`). Do NOT use `git add -u` as it stages all tracked changes repo-wide.
- **No parallel conflicts.** Never launch subagents that touch the same files simultaneously.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must be populated.

## Phase 1: Plan

1. **Read all docs** — Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full.
2. **Inventory reference skills** — List all skill directories in `.agents/skills/` matching `tech-*`, `style-*`, `optim-*`, and `domain-*`. Read each one. These contain guidance on technologies, code style, optimisation, and domain concepts.
3. **Scan code structure** — List all files in `src/` and `tests/`. Read module-level docstrings, class/function signatures, and imports — do NOT read full function bodies yet. If no code exists, note that.
4. **Identify gaps** — Determine what needs to be built, changed, or removed to align code with docs.
5. **Get HEAD SHA** — Run: `git rev-parse HEAD` and save the output.
6. **Write `docs/change_promise.toml`** — Use the Write tool to create this file. It MUST be valid TOML using the exact schema below. Every `[[tasks]]` entry MUST include all fields. Set `base_commit` to the SHA from step 5 and `created_at` to the current ISO 8601 timestamp.

```toml
[metadata]
base_commit = "<SHA from step 5>"
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

7. **Pretty-print the plan** — Run: `uvx prothon promise plan` and show its output to the user. This is the ONLY way to present the plan — do NOT create your own tables, summaries, or descriptions.
8. **Get approval** — Wait for the user to approve. Do not proceed until approved.

**Task sizing rules:**
- Each task must be **small enough** for a single subagent to complete independently
- Each task must be **well-scoped** with clear file boundaries — no two independent tasks should modify the same file
- Tasks must be **ordered** so dependencies come before dependents
- Every task MUST list the specific reference skills relevant to it
- Estimate line counts — these are checked with ±30% or ±30 lines tolerance (whichever is greater)

---

## Phase 2: Execute

For each task (respecting dependency order):

1. **Wait for dependencies** — All tasks listed in `dependencies` must be marked complete before starting.
2. **Launch subagent** — Spawn a subagent (type: general-purpose, fresh context) with the task loop prompt below.
3. **Independent tasks can run in parallel** — but never two tasks that touch the same files.
4. **After each subagent returns:**
   - If succeeded (task marked complete): continue to next task
   - If failed (`max_attempts` retries exhausted): report to user, ask skip/retry/abort
5. **Track progress** — Run `uvx prothon promise status` to see overall progress.

### Subagent Prompt Template

```
You are implementing a single task. One "attempt" is a full iteration of steps 3–5.
Before each attempt, check: if attempts >= {max_attempts}, stop and report failure.

1. READ CONTEXT:
   - Read these doc sections: {doc_sections}
   - Read these reference skills: {skill_paths}
   - Read these context files: {context_files}

2. IMPLEMENT:
   - Goal: {goal}
   - Files to create: {files_to_create}
   - Files to modify: {files_to_modify}
   - Files to remove: {files_to_remove}
   - Success criteria: {success_criteria}

3. QUALITY GATE:
   a) Stage selectively by explicit path:
      - Stage modified files: git add {files_to_modify}
      - Stage new files: git add {files_to_create}
      - Remove deleted files: git rm {files_to_remove}
   b) Run: pre-commit run --all-files --show-diff-on-failure
   c) If hooks auto-fixed files, re-stage the specific files and re-run pre-commit once
   d) If pre-commit still fails, increment attempts and go to step 2 to fix

4. COMMIT AND VERIFY (only after pre-commit passes):
   a) Commit: git commit -m "feat: {title}"
   b) Run: uvx prothon promise check {task_index}
   c) If promise check fails, increment attempts and go to step 2 to fix

5. IF ALL PASS:
   - Run: uvx prothon promise complete {task_index} {attempts}
   - Report success
```

---

## Phase 3: Verify

1. **Compliance check** — Load `prothon-compliance-checker` in a fresh context.
2. **Report results** — Present report and fix failures until compliant.
3. **Clean up** — Run `uvx prothon promise cleanup`.

## Guards

- **TOML only.** The plan is ALWAYS `docs/change_promise.toml`. No markdown plans.
- **No manual tables.** Use `uvx prothon promise plan` output only.
- **Doc integrity.** Do NOT modify SPEC, DESIGN, or PATTERNS.
- **Fresh context.** Use fresh subagents for implementation tasks.
