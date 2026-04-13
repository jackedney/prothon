## Operational Guards

### Selective Staging
Stage only task-related files by explicit path. NEVER use `git add -u`, `git add -A`, or `git add .`.

### Fresh Instances
Each subagent attempt gets a fresh instance. Never reuse sessions.

### Commit Workflow
After writing, stage explicitly and commit. Do NOT push to remote.

### Quality Gate
After implementation:
1. Type check: `uvx ty check src/ tests/` — fix ALL errors
2. Lint: `pre-commit run --all-files --show-diff-on-failure`
3. If hooks auto-fixed files, re-stage and re-run once. If still failing, EXIT with FAILURE.

### Prerequisite
Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full before any analysis or implementation.
