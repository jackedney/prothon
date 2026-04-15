# Change Promise TOML Format

Reference for writing `docs/change_promise.toml` during Phase 1 planning.

## Required Structure

Every `[[tasks]]` entry MUST include all fields shown below.

```toml
[metadata]
base_commit = "<SHA from git rev-parse HEAD>"
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
context_files = ["src/middleware.py", "src/config.py", "docs/references/modules.md"]
doc_sections = ["DESIGN.md#Authentication", "PATTERNS.md#Error-Handling"]
reference_skills = ["tech-fastapi", "style-python"]
dependencies = []
completed = false
attempts = 0
```

## Field Guidelines

- **Test files are optional.** Only include a test file in `files_to_create` when the task introduces testable business logic. Trivial modules (constants, type definitions, pass-throughs) don't need tests.
- **Reference files as context** — When a task modifies a specific module, include the corresponding reference file in `context_files`. For example, if modifying `src/prothon/promise.py`, include `"docs/references/modules.md"` so the subagent can load the relevant signatures section. If the reference file doesn't exist, omit it.
- **DRY. YAGNI. TDD.** Embed complete code concepts or context rather than vague descriptions ("add validation").
- **Bite-sized tasks** — 2-5 minutes of work each.
