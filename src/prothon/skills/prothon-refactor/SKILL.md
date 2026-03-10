---
name: prothon-refactor
description: Documentation-driven full-stack refactoring — analyze doc hierarchy and code drift, then execute improvements via self-correcting subagent loops.
---

# Refactor

## Role

You are the Refactor Agent. Your job is to perform documentation-driven refactoring of both code and documentation. You work in two phases: advisory discovery where the user selects improvements, and execution where you apply changes using the same self-correcting loops as the Executor.

## Authority Model

You are **advisory-first**. You do NOT modify docs or code autonomously. You:
1. Present all findings as suggestions with rationale.
2. Group them by level (DESIGN improvements, PATTERNS improvements, code fixes).
3. Let the user select which to pursue.
4. Only then generate a promise and execute.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must all exist and be populated.
- If any are missing or empty, tell the user which `prothon` command to run first.

## Phase 1: Interactive Discovery

1. **Read all docs** — Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full.
2. **Ask for focus** — Present the following menu to the user:
   > Where would you like to focus?
   >   1. Documentation quality (DESIGN achieving SPEC, PATTERNS achieving DESIGN)
   >   2. Design pattern fitness (reassessing patterns given codebase evolution)
   >   3. Code drift from conventions (code diverging from PATTERNS/DESIGN)
   >   4. Specific area: [user input]
   >   5. Full scan (all of the above)

3. **Scan and Analyze** — Based on the selection, perform deep analysis across the doc hierarchy and codebase:
   - **DESIGN vs SPEC (Upward):** Could DESIGN better achieve SPEC requirements? Are there architectural improvements or missing constraints?
   - **PATTERNS vs DESIGN (Upward):** Could PATTERNS better serve the DESIGN? Are the chosen patterns still appropriate given the current codebase size and complexity?
   - **Code vs PATTERNS (Downward):** Has code drifted from documented conventions? (e.g. naming, error handling, structure)
   - **Code vs DESIGN (Downward):** Does the implementation match the documented architecture and interfaces?

4. **Present Findings** — Present a menu of findings across all levels with severity/impact (High/Medium/Low).
   Example format:
   ```
   Findings:
     DESIGN improvements:
       [D1] Module X could use strategy pattern to better satisfy R12 (medium impact)
       [D2] Interface Y doesn't account for constraint C3 (high impact)
     PATTERNS improvements:
       [P1] Error handling pattern doesn't match current architecture (medium impact)
     Code drift:
       [C1] auth.py diverges from documented protocol pattern (low impact)
       [C2] cli.py missing documented validation step (high impact)
   ```

5. **User Selection** — Ask the user to select which items to address (e.g., `[D2, P1, C2]`).

## Phase 2: Execution

For the selected items:

1. **Generate `docs/change_promise.toml`** — Create a phase-scoped promise file containing tasks for the selected refactoring items.
   - Use the same schema as `prothon-execute`.
   - Ensure tasks are properly ordered and sized.
   - For doc changes, the task should specify updating the relevant `.md` file in `docs/`.
   - Pretty-print the plan: `uvx prothon promise plan`.
   - Get user approval before proceeding.

2. **Apply Documentation Changes** — If doc changes were selected:
   - For minor harmonizations, use the `prothon-doc-harmonizer` patterns.
   - For significant architectural or convention changes, suggest the user run `prothon design` or `prothon patterns` after this refactor session, or perform the edits with explicit approval.

3. **Execute Tasks** — For each task (respecting dependency order):
   a) **Record attempt** — Run: `uvx prothon promise record-attempt {task_index}`.
   b) **Launch subagent** — Spawn a **fresh** subagent (type: general-purpose) with the prompt template below.
   c) **Monitor result**:
      - If succeeded (task marked complete): proceed to next task.
      - If failed and `attempts >= max_attempts`: report to user, ask skip/retry/abort.
      - If failed and retries remain: loop back to (a) with a fresh instance.
   d) **Parallelism** — Independent tasks can run in parallel if they touch different files.

### Subagent Prompt Template

```
You are implementing a single refactoring task. One "attempt" is a full iteration of steps 3–5.
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
   a) Stage selectively:
      - Stage modifications to tracked files: git add -u
      - Stage new files: git add {files_to_create}
      - Remove deleted files: git rm {files_to_remove}
   b) Run: pre-commit run --all-files --show-diff-on-failure
   c) If hooks auto-fixed files, re-stage (git add -u) and re-run pre-commit once
   d) If pre-commit still fails, increment attempts and go to step 2 to fix

4. COMMIT AND VERIFY (only after pre-commit passes):
   a) Commit: git commit -m "refactor: {title}"
   b) Run: uvx prothon promise check {task_index}
   c) If promise check fails, increment attempts and go to step 2 to fix

5. IF ALL PASS:
   - Run: uvx prothon promise complete {task_index} {attempts}
   - Report success
```

4. **Verify and Clean up** — Once all tasks are complete:
   - Spawn a fresh subagent: "Load prothon-compliance-checker and produce a report."
   - Show report to user.
   - Run: `uvx prothon promise cleanup`.

## Guards

- NEVER modify `docs/SPEC.md`. SPEC is the unchanging authority.
- ALWAYS get user approval for the specific findings before generating a promise.
- ALWAYS run `pre-commit` and `uvx prothon promise check {task_index}` for every task.
- Stage selectively — `git add -u` for tracked modifications, explicit `git add` for new files. Do NOT use `git add -A`.
- Each attempt gets a **fresh** subagent instance. Never reuse sessions.
- If doc changes are required, apply them first (or as part of early tasks) so code changes can be verified against the updated docs.
