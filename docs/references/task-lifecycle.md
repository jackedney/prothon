# Task Lifecycle

The 7-step lifecycle for each task in the `prothon execute` workflow. This is the behavioral contract for the execution orchestrator, serving SPEC requirements R27-R33.

## Steps

1. **Dependency check** — wait for all tasks whose `task_id` appears in this task's `dependencies` list to be marked complete.
2. **Read context** — read `doc_sections`, `reference_skills`, and `context_files`.
3. **Implement** — create, modify, or remove files per the plan.
4. **Quality gate (R32)** — run `pre-commit run --all-files`. The agent must fix all reported errors and warnings project-wide (including pre-existing ones) before proceeding.
5. **Commit** — Stage only files declared in `files_to_create`, `files_to_modify`, and `files_to_remove`, plus any files auto-fixed by the quality gate in step 4. Then commit with `--no-verify`. Note: `--no-verify` is safe because step 4 already ran the full hook suite.
6. **Plan verification (R31)** — run `check_task()` which uses `git diff <base_commit>`.
7. **Completion** — mark the task complete via `complete_task()`.

## Retry Behavior

If step 4 or step 6 fails, the subagent calls `record_attempt()` and retries from step 3. The retry is gated by `record_attempt()` succeeding — if `attempts >= max_attempts`, `record_attempt()` raises `MaxAttemptsExceeded` rather than incrementing, which halts the retry loop. The orchestrator then asks the user to skip, retry (reset counter), or abort.

## Fix Mandate

Step 4 enforces **Global Health Enforcement** — the agent must fix all errors/warnings project-wide (including pre-existing ones) before a task is verified. This prevents accumulation of tech debt.
