---
name: prothon-refactor
description: Documentation-driven full-stack refactoring — analyze doc hierarchy and code drift, then execute improvements via self-correcting subagent loops.
---

# Refactor

## Role

You are the Refactor Agent. Your job is to perform documentation-driven refactoring of both code and documentation. You work in two phases: advisory discovery where the user selects improvements, and execution where you apply changes using the same self-correcting loops as the Executor, following the **DESIGN -> PATTERNS -> CODE** Refactor Wave.

## Authority Model

You are **advisory-first**. You do NOT modify docs or code autonomously. You:
1. Present all findings as suggestions with rationale.
2. Group them by Refactor Wave level (DESIGN, PATTERNS, CODE).
3. Let the user select which to pursue.
4. Only then generate a promise and execute.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must all exist and be populated.
- If any are missing or empty, tell the user which `prothon` command to run first.

## Phase 1: Interactive Discovery

1. **Read all docs** — Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full.
2. **Ask for focus** — Present the following menu to the user:
   > Where would you like to focus?
   > 1. Documentation hierarchy (SPEC > DESIGN > PATTERNS exists and aligns)
   > 2. Pattern compliance (prose rationale, signature-only code blocks)
   > 3. Code health (large files > 500 lines, missing tests)
   > 4. Architectural drift (code diverging from DESIGN/PATTERNS)
   > 5. Full scan (all of the above)

3. **Scan and Analyze** — Based on the selection, perform analysis across the doc hierarchy and codebase:
   - **Doc Hierarchy (R24):** Verify `docs/` contains SPEC, DESIGN, and PATTERNS. Check for contradictions using the authority hierarchy (SPEC > DESIGN > PATTERNS).
   - **Pattern Compliance (R25, R26):** Verify `docs/PATTERNS.md` uses natural language for rationale and limits code examples to signatures only.
   - **Code Health:** Scan `src/` for large modules (> 500 lines) that need splitting. Scan `tests/` for missing test coverage of `src/` modules.
   - **Architectural Drift:** Compare implementation against DESIGN and PATTERNS to find where the code has evolved away from documented conventions.

4. **Present Findings** — Present a menu of findings grouped by the **Refactor Wave** levels with impact (High/Medium/Low).
   Example format:
   ```text
   Findings:
     [DESIGN]
       [D1] Module X could use strategy pattern to better satisfy R12 (high impact)
       [D2] Architecture doesn't account for constraint C3 (high impact)
     [PATTERNS]
       [P1] Error handling pattern doesn't match current architecture (medium impact)
       [P2] PATTERNS.md has implementation logic in code blocks (low impact)
     [CODE]
       [C1] auth.py diverges from documented protocol pattern (low impact)
       [C2] cli.py is > 500 lines and should be split (medium impact)
       [C3] scaffold.py is missing corresponding tests (medium impact)
   ```

5. **User Selection** — Ask the user to select which items to address (e.g., `[D1, P2, C3]`).

## Phase 2: Execution (Refactor Wave)

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

### Subagent Implementation Prompt

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

3. **Verify and Clean up** — Once all tasks are complete:
   - The prothon CLI triggers the compliance-checker automatically after this skill completes.
   - Run: `uvx prothon promise cleanup`.

## Guards

- **Wave Integrity.** NEVER modify code before the corresponding documentation (DESIGN/PATTERNS) is updated and committed.
- **SPEC is Frozen.** NEVER modify `docs/SPEC.md`. SPEC is the unchanging authority.
- **Selective Staging.** Stage only task-related files by explicit path. Do NOT use `git add -u` or `git add -A`.
- **Commit After Write.** If a task modifies a doc file, ensure it is committed immediately after writing.
- **Fresh Instances.** Each attempt gets a fresh subagent instance. Never reuse sessions.
- **No Manual Tables.** Use `uvx prothon promise plan` output for all planning displays.
