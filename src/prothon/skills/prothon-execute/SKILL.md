---
name: prothon-execute
description: Align source code to documentation — generates an enriched change promise, then executes tasks via self-correcting subagent loops.
---

# Execute

## Role

You are the Executor. Your job is to make the source code match the documentation. You generate an enriched change promise (the plan), get user approval, then execute each task via a self-correcting subagent loop.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must all exist and be populated
- If any are missing or empty, tell the user which `prothon` command to run first

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
2. **Launch subagent** — Launch a fresh subagent (Task tool, `subagent_type: general-purpose`) with the task loop prompt below.
3. **Independent tasks can run in parallel** — but never two tasks that touch the same files.
4. **After each subagent returns:**
   - If succeeded (task marked complete): continue to next task
   - If failed (3 retries exhausted): report to user, ask skip/retry/abort
5. **Track progress** — Run `uvx prothon promise status` to see overall progress.

### Subagent Prompt Template

```
You are implementing a single task. Follow this loop:

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

3. CHECK:
   a) Run: poe check
   b) Stage files: git add {all task files}
   c) Commit: git commit -m "feat: {title}"
   d) Run: uvx prothon promise check {task_index}

4. IF ANY CHECK FAILS:
   - Read the error output
   - Fix the issues
   - Go to step 3 (max 3 total attempts)

5. IF ALL PASS:
   - Run: uvx prothon promise complete {task_index} {attempts}
   - Report success
```

**Key details:**
- Subagent commits before promise check — `git diff <base_commit>` sees committed changes
- `poe check` runs the full quality suite (ruff, ty, bandit, vulture, complexipy, tests)
- Max 3 retries — after 3 failures, surface the error to the orchestrator
- Keep your own context lean: reference file paths in subagent prompts — do NOT paste file contents

---

## Phase 3: Verify

1. **Run compliance check** — Launch a subagent (Task tool, `subagent_type: general-purpose`, fresh context) with this prompt:
   > Load the prothon-compliance-checker skill and execute it. Read all docs and all source code, then produce a compliance report.

2. **Report results** — Present the compliance report to the user. If there are failures, fix them and re-check until compliance passes or the remaining issues need user input.

3. **Clean up** — Run: `uvx prothon promise cleanup` to remove the promise file. Each execution generates a fresh promise, so stale ones must not persist.

## Guards

- Do NOT write markdown plan files — no `docs/PLAN.md`, no `plan.md`, no markdown summaries. The plan is ALWAYS `docs/change_promise.toml` in TOML format.
- Do NOT create your own plan tables, summaries, or wave diagrams — ALWAYS use `uvx prothon promise plan` output and nothing else.
- Do NOT improvise an alternative plan format — the TOML schema above is the contract. Every field is required.
- Do NOT modify doc files (SPEC.md, DESIGN.md, PATTERNS.md) — if docs seem wrong, flag it to the user
- Do NOT skip the planning phase — always generate `docs/change_promise.toml` and get approval first
- Do NOT launch subagents that modify the same files in parallel — this causes conflicts
- Do NOT paste file contents into subagent prompts — reference paths and let subagents read
- Do NOT read full file contents yourself unless absolutely necessary for planning — stay lean
