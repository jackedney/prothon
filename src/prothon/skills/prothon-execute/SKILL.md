---
name: prothon-execute
description: "[What] Align source code to documentation. [When] Use to implement features or fixes based on the doc hierarchy. [Capabilities] Wave-based phase planning, subagent-driven development loops with two-stage review, and automated verification."
---

# Execute

## Role

You are the Executor. Align source code to documentation by determining the next logical phase of work, generating a phase-scoped change promise, and implementing it via fresh-context subagent loops.

## Critical

- **Plan first.** Never skip the approval of `docs/change_promise.toml`.
- **Phase-scoped.** Plan one small testable phase (3-7 tasks), not the entire project.
- **Lean context.** Reference file paths in prompts; do NOT paste full contents.
- **No parallel conflicts.** Never launch subagents that touch the same files simultaneously.

## Prerequisites

- `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` must be populated.

## Phase 1: Plan (Wave Determination)

You are stateless between invocations. Determine "what to do next" by inspecting reality:

1. **Read all docs** — Read `docs/SPEC.md`, `docs/DESIGN.md`, and `docs/PATTERNS.md` in full to understand the target state.
2. **Scan existing code** — List all files in `src/` and `tests/`. Read signatures and imports to understand what's already built. Scan git history to see recent changes.
3. **Identify gaps** — Diff the docs against the code to find implementation gaps.
4. **Select next phase** — Pick a small, testable chunk of work (3–7 tasks) that moves the project toward alignment. Prioritize foundational dependencies (e.g., data models before CLI).
5. **Inventory reference skills** — List all skill directories in `.agents/skills/` matching `tech-*`, `style-*`, `optim-*`, and `domain-*`.
6. **Inventory reference docs** — List all files in `docs/references/`. These are progressive disclosure documents containing per-module API signatures and topic-specific reference material.
7. **Get HEAD SHA** — Run: `git rev-parse HEAD`.
8. **Write `docs/change_promise.toml`** — Create this file covering ONLY the selected phase. See `references/promise-format.md` for the full TOML schema and field guidelines. Key rules: bite-sized tasks (2-5 minutes each), DRY/YAGNI/TDD, every `[[tasks]]` entry includes all fields.
9. **Pretty-print the plan** — Run: `uvx prothon promise plan` and show its output.
10. **Get approval** — Wait for user approval before proceeding.

---

## Phase 2: Execute (Subagent-Driven Development)

> **Detail:** See `references/execution-detail.md` for the full retry loop, two-stage review procedure, and Phase 3 cleanup steps.

For each task (respecting dependency order): record attempt → launch fresh implementer subagent (`./implementer-prompt.md`) → spec review (`./spec-reviewer-prompt.md`) → code quality review (`./code-quality-reviewer-prompt.md`). Both reviewers must approve before moving to the next task. Independent tasks can run in parallel if they touch different files.

## Phase 3: Verify & Advance

After all tasks complete: compliance check runs automatically, then `uvx prothon promise cleanup`, then tell user to run `prothon execute` again for the next phase.

## Guards

- **TOML only.** The plan is ALWAYS `docs/change_promise.toml`. No markdown plans.
- **No manual tables.** Use `uvx prothon promise plan` output only.
- **Doc integrity.** Do NOT modify SPEC, DESIGN, or PATTERNS.
- Follow the [shared operational guards](_shared/guards.md).
- **Phase-scoped.** Focus on a single testable phase, not the entire project.
- **No bypassing.** Do NOT ignore `pre-commit` or `promise check` failures — they MUST trigger a retry or abort.
- **Line estimates.** Checked with ±30% or ±30 lines tolerance.
