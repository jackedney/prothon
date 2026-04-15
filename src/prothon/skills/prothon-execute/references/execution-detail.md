# Execution Detail Reference

Detailed Phase 2 and Phase 3 procedures for the execute workflow.

## Phase 2: Execute (Subagent-Driven Development)

For each task in the promise (respecting dependency order):

1. **Orchestrate Retries & Two-Stage Review** — While `attempts < max_attempts` and task is not `completed`:
   a) **Record attempt** — Run: `uvx prothon promise record-attempt {task_index}` (counts every attempt, including the one about to start).
   b) **Launch Implementer Subagent** — Spawn a **fresh** subagent using `./implementer-prompt.md`. When the task's `context_files` includes a `docs/references/` file (e.g., `docs/references/modules.md`), the subagent should read the relevant section for the module it's modifying to understand the existing API surface before making changes. Keep this session alive until both reviewers approve. If it asks questions before implementing, answer them.
   c) **Launch Spec Reviewer Subagent** — Once the implementer finishes, spawn a **fresh** subagent using `./spec-reviewer-prompt.md` to confirm the code matches the specification.
      - If it reports gaps/issues, send the feedback to the **still-open Implementer Subagent** to fix. Re-launch a fresh spec reviewer until approved.
   d) **Launch Code Quality Reviewer Subagent** — Once spec compliance is approved, spawn a **fresh** subagent using `./code-quality-reviewer-prompt.md`.
      - If it reports issues, send the feedback to the **still-open Implementer Subagent** to fix. Re-launch a fresh code quality reviewer until approved.
   Once both reviewers approve, the implementer session closes.
   e) **Monitor Result**:
      - If all reviewers approve and verifications pass (task marked complete): Proceed to next task.
      - If the process fails and `attempts >= max_attempts`: report failure to user and ask skip/retry/abort.
      - Otherwise, loop back to step (a) to start a new attempt.

2. **Parallelism** — Independent tasks can run in parallel if they touch different files.

*(The prompts `implementer-prompt.md`, `spec-reviewer-prompt.md`, and `code-quality-reviewer-prompt.md` are located in this skill directory.)*

## Phase 3: Verify & Advance

1. **Compliance Check** — The prothon CLI triggers the compliance-checker automatically after this skill completes.
2. **Report & Clean up** — Run `uvx prothon promise cleanup`.
3. **Next Phase** — Tell the user: "Phase complete. Run `prothon execute` again to begin the next phase."
