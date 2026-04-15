# Refactor Execution Detail

Detailed Phase 2 execution procedures including subagent prompt template.

## Wave 0 Execution (if doc quality items were selected)

Execute Wave 0 items first. These produce only DESIGN.md and PATTERNS.md changes:
1. Generate a promise with Wave 0 tasks (DESIGN tasks first, then PATTERNS tasks).
2. Execute tasks using the standard subagent loop (see below).
3. After all Wave 0 tasks complete, run the **doc-harmonizer** automatically to ensure DESIGN<->PATTERNS consistency.
4. Then proceed to Wave 1 execution below.

## Wave 1 Execution

For the selected items, follow the **DESIGN -> PATTERNS -> CODE** Wave:

1. **Generate `docs/change_promise.toml`** — Create a phase-scoped promise file containing tasks for the selected refactoring items.
   - **Task Order:** Order tasks by Wave level (DESIGN tasks first, then PATTERNS, then CODE).
   - **Doc Tasks:** For doc changes, the task should specify updating the relevant `.md` file in `docs/`.
   - **Code Tasks:** CODE tasks must reference the specific documentation heading they are aligning with.
   - Run: `uvx prothon promise plan` and show the output.
   - Get user approval before proceeding.

2. **Execute Tasks** — For each task (respecting dependency order):
   a) **Record attempt** — Run: `uvx prothon promise record-attempt {task_index}`.
   b) **Launch subagent** — Spawn a **fresh** subagent with the prompt template below.
   c) **Monitor result**:
      - If succeeded (task marked complete): proceed to next task.
      - If failed and `attempts >= max_attempts`: report to user, ask skip/retry/abort.
      - If failed and retries remain: loop back to (a) with a fresh instance.
   d) **Parallelism** — Independent tasks can run in parallel if they touch different files.

## Subagent Implementation Prompt

```text
You are implementing a single refactoring task with fresh context. You MUST close the session on completion.

1. LOAD CONTEXT:
   - Read these doc sections: {doc_sections}
   - Activate these reference skills: {reference_skills}
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
   e) Commit: git commit -m "refactor: {title}"
   f) Final check: Run `uvx prothon promise check {task_index}`

4. EXIT:
   - If `promise check` passed:
     - Run: `uvx prothon promise complete {task_index}`
     - Report SUCCESS and close session.
   - If any step failed:
     - Report FAILURE with context on what went wrong and close session.
```

## Post-Execution

Once all tasks are complete:
- The prothon CLI triggers the compliance-checker automatically after this skill completes.
- Run: `uvx prothon promise cleanup`.
