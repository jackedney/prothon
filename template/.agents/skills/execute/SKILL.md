---
name: execute
description: Align source code to documentation — assesses scope, then either implements directly or plans and delegates to subagents.
---

# Execute

## Role

You are the Executor. Your job is to make the source code match the documentation. You assess the scope of work, then either implement directly (small changes) or plan and delegate to subagents (large changes).

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must all exist and be populated
- If any are missing or empty, tell the user which `prothon` command to run first

## Phase 1: Assess (always)

1. **Read all docs** — Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full.
2. **Inventory reference skills** — List all skill directories in `.agents/skills/` matching `tech-*`, `style-*`, `optim-*`, and `domain-*`. Read each one. These contain guidance on technologies, code style, optimisation, and domain concepts.
3. **Scan code structure** — List all files in `src/` and `tests/`. Read module-level docstrings, class/function signatures, and imports — do NOT read full function bodies yet. If no code exists, note that.
4. **Identify gaps** — Determine what needs to be built, changed, or removed to align code with docs.
5. **Classify scope** — Based on the gaps:
   - **Small:** 1-2 files affected, single concern, no dependency ordering needed → go to **Small Path**
   - **Large:** 3+ files affected, multiple independent concerns, benefits from parallelism → go to **Large Path**

---

## Small Path

For small changes, implement directly without subagents.

6. **Read the affected files in full** — Now read the complete content of files you need to modify or that inform the change.
7. **Implement** — Write the code changes directly.
8. **Generate change promise** — Write a single-task `docs/change_promise.toml` for the change you just made:

```toml
[metadata]
plan_source = "inline"

[[tasks]]
title = "<what you changed>"
success_criteria = "<how to verify it's correct>"
files_to_modify = ["<files you modified>"]
files_to_create = ["<files you created>"]
files_to_remove = ["<files you removed>"]
expected_lines_added = <estimate>
expected_lines_removed = <estimate>
completed = false
```

9. **Check the promise** — Run: `python -m prothon.promise check 0`
   - If **PASS** → run `python -m prothon.promise complete 0`
   - If **DISCREPANCY** → review your own work against the report. Fix issues or accept the discrepancy (you're already in context, no senior-dev needed). Then mark complete.

10. **Verify** — Launch a compliance-checker subagent (see Verify phase below).

---

## Large Path

For large changes, stay lean — you are an orchestrator, not an implementer. Keep your context small by letting subagents do the heavy reading and writing.

### Plan

6. **Write the plan** — Write an implementation plan to `docs/PLAN.md`:

```markdown
# Implementation Plan

## Tasks

### Task 1: <title>
- **Goal:** What this task accomplishes
- **Files:** Which files to create or modify
- **Context files:** Which existing files the subagent should read to understand the surrounding code
- **Reference skills:** Which `tech-*`, `style-*`, `optim-*`, or `domain-*` skills to read
- **Doc sections:** Which specific sections of SPEC.md, DESIGN.md, or PATTERNS.md are relevant (by heading, not full content)
- **Dependencies:** Which other tasks must complete first (if any)
- **Acceptance:** How to verify this task is done

### Task 2: <title>
...
```

Each task must be:
- **Small enough** for a single subagent to complete independently
- **Well-scoped** with clear file boundaries — no two independent tasks should modify the same file
- **Ordered** so that dependencies come before dependents

Every task MUST list the specific reference skills relevant to it. For example, a task that writes Python code using Click should list `style-python`, `tech-click`, and any relevant `domain-*` or `optim-*` skills.

7. **Get approval** — Present the plan to the user. Do not proceed until approved.

### Generate Change Promise

8. **Write the change promise** — Generate `docs/change_promise.toml` from the plan. For each task in `docs/PLAN.md`, create a TOML entry:

```toml
[metadata]
plan_source = "docs/PLAN.md"

[[tasks]]
title = "<task title from plan>"
success_criteria = "<from Acceptance field>"
files_to_modify = ["<from Files field — existing files>"]
files_to_create = ["<from Files field — new files>"]
files_to_remove = ["<files to delete, if any>"]
expected_lines_added = <your estimate>
expected_lines_removed = <your estimate>
completed = false
```

Estimate line counts based on the scope of each task. Be reasonable — these are checked with ±50% or ±50 lines tolerance (whichever is greater).

### Execute

9. **Launch subagents** — For each task (or group of independent tasks), launch a subagent (Task tool, `subagent_type: general-purpose`, fresh context) with a prompt that tells it to:
   - Read the specific doc sections listed in the task (by file path and heading)
   - Read the reference skills listed in the task (by file path, e.g., `.agents/skills/tech-click/SKILL.md`)
   - Read the context files listed in the task
   - Then implement the goal described in the task
   - Write code, not just research

   **Keep your own context lean:** reference file paths in subagent prompts — do NOT paste file contents into the prompt. Subagents read files themselves.

   Launch independent tasks in parallel. Wait for blocking tasks to complete before launching dependents.

### Verify Each Task

10. **Check promise after each subagent completes** — Run: `python -m prothon.promise check <task-index>`

    - If **PASS** → run `python -m prothon.promise complete <task-index>`. No additional agent needed.
    - If **DISCREPANCY** → launch a senior-dev subagent (Task tool, `subagent_type: general-purpose`, fresh context) with a prompt that includes:
      - The discrepancy report (paste the output from the check command)
      - The task index and title
      - The file paths from the promise
      - Instruction: "Read the senior-dev skill at `.agents/skills/senior-dev/SKILL.md` and follow it."

    The senior-dev will either fix the code or accept the discrepancy, then mark the task complete.

11. **Track progress** — Run `python -m prothon.promise status` to see overall progress. Continue until all tasks are complete.

---

## Verify (always)

12. **Run compliance check** — Launch a subagent (Task tool, `subagent_type: general-purpose`, fresh context) with this prompt:
    > Read the compliance-checker skill at `.agents/skills/compliance-checker/SKILL.md` and execute it. Read all docs and all source code, then produce a compliance report.

13. **Report results** — Present the compliance report to the user. If there are failures, fix them and re-check until compliance passes or the remaining issues need user input.

## Guards

- Do NOT modify doc files (SPEC.md, DESIGN.md, PATTERNS.md) — if docs seem wrong, flag it to the user
- Do NOT skip the planning phase on the large path — always write `docs/PLAN.md` and get approval first
- Do NOT launch subagents that modify the same files in parallel — this causes conflicts
- Do NOT paste file contents into subagent prompts — reference paths and let subagents read
- On the large path, do NOT read full file contents yourself unless absolutely necessary for planning — stay lean
- Do NOT skip the change promise — always generate `docs/change_promise.toml` before launching implementation subagents
