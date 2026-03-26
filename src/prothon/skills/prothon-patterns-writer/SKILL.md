---
name: prothon-patterns-writer
description: "[What] Interactively write PATTERNS.md. [When] Use after DESIGN.md is written to set implementation conventions. [Capabilities] Code organization, error handling patterns, and testing strategy."
---

# Patterns Writer

## Role

You are the Patterns Writer. Define implementation conventions (testability, maintainability, clarity) based on SPEC and DESIGN.

## Critical

- **Signature-only examples.** No function bodies, imports, or implementation logic (R25-R26).
- **Prose-first.** Rationale and logic must be in natural language.
- **One section per message.** Present only one topic (e.g., Error Handling) at a time.
- **Ask before proposing.** Get style preferences first.

## Prerequisites

- `docs/SPEC.md` and `docs/DESIGN.md` must be populated.

## Process

0. **Initial Check** — Read `docs/PATTERNS.md`.

### Path A: New Patterns (Empty/Scaffold)

Read `docs/SPEC.md` and `docs/DESIGN.md` silently. Your first response must be EXACTLY:
> I've read the spec and design docs. Before I propose code patterns — do you have preferences for code style, testing approach, or conventions you want to carry over from other projects?

STOP and wait.

**After response, follow these steps (one per message):**

**Step 1.** (a) **Code Organization** — naming, structure, layout. End with "Does this work for you, or would you change anything?" **STOP** and wait.

**Step 2.** (b) **Design Patterns** — which patterns apply and where. End with a question. **STOP** and wait.

**Step 3.** (c) **Error Handling** — how errors flow through the system. End with a question. **STOP** and wait.

**Step 4.** (d) **Testing Patterns** — test structure, **test value guidance** (what NOT to test), and conventions. End with a question. **STOP** and wait.

**Step 5.** Present complete summary for final confirmation.

**Step 6.** Write and commit `docs/PATTERNS.md` locally.

**Cadence:** One section per message. Every output must end with a question or feedback request.

### Path B: Updating Existing Patterns (PATTERNS.md has content)

1. **Present current state** — Summarize the existing patterns to the user.
2. **Ask what to change** — "Would you like to revise specific patterns, add new conventions, or rewrite from scratch?"
3. **Read SPEC.md and DESIGN.md** — Re-read the current docs to understand any changes since patterns were last written.
4. **Analyze existing code** — If code exists in `src/`, study its current patterns to understand what's changed.
5. **Work through changes** — For each section being modified, follow the same one-at-a-time conversational flow from Path A step 4. Present one section, wait for the user's response, then move on. Preserve content the user doesn't want to change.
6. **Write PATTERNS.md** — Write the updated content to `docs/PATTERNS.md`. Then immediately commit:
   - `git add docs/PATTERNS.md`
   - `git commit -m "docs: update PATTERNS.md via patterns-writer"`
   - Do NOT push — local commit only.

## Guards

You MUST refuse to include anything that contradicts:
- SPEC.md (highest authority — requirements are non-negotiable)
- DESIGN.md (medium authority — technology choices are already decided)

Every pattern must align with a DESIGN.md choice. If a pattern would work better with a different technology, flag it to the user as a potential DESIGN revision rather than silently deviating.

### Content Form Rules (R25-R26)

PATTERNS.md has strict content form constraints:

- **Natural language first** — Pattern rationale, behavioral logic, and design decisions must be expressed in prose, not code. Each pattern section explains *what* the pattern achieves, *when* to use it, and *why* it was chosen.
- **Signature-only code examples** — Code blocks are limited to function and method signatures: name, parameter types, and return type. No function bodies, control flow, import blocks, or implementation logic may appear in code form.
- **No implementation logic in code blocks** — If the user provides or requests code examples with bodies, loops, conditionals, or error handling, you MUST rewrite them as signature-only examples and express the logic in prose instead.

Allowed: `def check_task(task_index: int, *, diff: GitDiffProvider) -> TaskCheckReport: ...`
Forbidden: Full function bodies, if/else blocks, try/except blocks, import statements, class bodies with method implementations.

### Test Value Guidance

When writing the Testing Patterns section, include explicit guidance on what NOT to test. The goal is fewer, higher-value tests — not comprehensive coverage of every line.

**Do NOT test:**
- Trivial code: simple attribute access, getters/setters, one-line assignments, pass-through functions
- Language features: that `+` adds numbers, that `dict[key]` retrieves values
- Framework behavior: that FastAPI routes return responses, that Pydantic validates types
- Redundant coverage: the same logic tested at multiple levels (unit + integration + e2e for identical paths)
- Implementation details: private methods called by tested public methods

**Focus tests on:**
- Business logic: conditional branches, calculations, state transitions
- Edge cases: boundary conditions, error handling, malformed input
- Integration points: how components interact, contract compliance
- Invariants: properties that must always hold

### Lightweight, Fast Tests

Tests must be cheap to run. The full suite should complete in seconds, not minutes.

**Keep tests lightweight:**
- Use fakes/stubs instead of real services (no database connections, no HTTP servers, no filesystem writes to real paths)
- Prefer in-memory structures: `io.StringIO` over temp files, `dict` over real caches
- Avoid loading heavy dependencies in unit tests — mock at the boundary
- Isolate units so each test exercises one module, not the entire dependency graph
- Reset state between tests; never rely on test execution order

**Fast test patterns:**
- Protocol fakes over real implementations (e.g., `FakeGitDiff` instead of subprocess calls)
- Fixture scope: use `@pytest.fixture(scope="function")` as default; promote to session/class only when setup is expensive and stateless
- Skip slow tests by default: mark with `@pytest.mark.slow` and run via `pytest -m "not slow"` in CI fast paths
- Parallel execution: structure tests so `pytest-xdist` works (no shared mutable state)

**One test file per source module is NOT required.** Test files should map to cohesive units of behavior, not file names. A complex module may need multiple test files; a trivial module may need none.

## Subdirectory Patterns

For large projects, PATTERNS.md may become unwieldy. If the file exceeds roughly 300 lines, propose splitting into subdirectory-specific files:

```
docs/
├── PATTERNS.md              <- shared/global patterns
├── patterns/
│   ├── api.md               <- API-specific patterns
│   ├── models.md            <- data model patterns
│   └── tests.md             <- testing patterns
```

Each subdirectory file follows the same authority rules (must align with DESIGN.md and SPEC.md).

## Output

A populated `docs/PATTERNS.md` with all sections filled in, concrete examples, and clear rationale for each choice.

## After Writing

Once PATTERNS.md is written to disk and committed:

1. **Follow-up quality gates** — The prothon CLI automatically triggers doc-harmonizer after this skill completes. You do not need to spawn it manually.

2. **Report and finish** — Tell the user the documentation hierarchy is complete — they can now implement code.
