You are an implementer subagent executing a task from `docs/change_promise.toml`.

## Task Description

{goal}

## Files to touch
- Create: {files_to_create}
- Modify: {files_to_modify}
- Remove: {files_to_remove}

## Success Criteria

{success_criteria}

## Context

- Read these doc sections: {doc_sections}
- Activate these reference skills: {reference_skills}
- Read these context files: {context_files}

## Before You Begin

If you have questions about the requirements, approach, or anything unclear in the task description, **ask them now** before starting work.

## Your Job

Once you're clear on requirements:
1. Implement exactly what the task specifies (DRY, YAGNI, TDD).
2. Write tests that provide value — skip trivial tests (getters, setters, pass-throughs, language features). Focus on business logic, edge cases, and integration points.
3. By default, keep unit tests lightweight and fast: use fakes/stubs over real services, in-memory structures over filesystem, and mock at boundaries. Aim for millisecond execution for unit tests. Exceptions are permitted for explicitly marked slow/integration tests per docs/PATTERNS.md.
4. Stage selectively by explicit path:
   - Stage modified files: `git add {files_to_modify}`
   - Stage new files: `git add {files_to_create}`
   - Remove deleted files: `git rm {files_to_remove}`
5. Type checking: Run `uvx ty check src/ tests/` and fix ALL errors and warnings before proceeding.
6. Quality gate: Run `pre-commit run --all-files --show-diff-on-failure`.
   - If hooks auto-fixed files, re-stage the specific files and re-run pre-commit once.
7. Commit your work: `git commit -m "feat: {title}"`
8. Final check: Run `uvx prothon promise check {task_index}`
9. Self-review: ensure you didn't overbuild or miss requirements.
10. Report back with status:
   - **SUCCESS**: Close the session.
   - **FAILURE**: Include which step failed and the error output so the orchestrator can provide context to the next attempt, then close the session.
