---
name: domain-doc-driven-dev
description: Domain knowledge -- documentation-driven development concepts for correct implementation
user-invocable: false
---

# Documentation-Driven Development

> Relevance: Prothon's core value proposition is a three-level documentation hierarchy that keeps AI agents aligned. Developers must understand authority flow, separation of concerns, and compliance semantics to implement doc agents, harmonization, and verification correctly.

## Core Concepts

**Three-level hierarchy:** SPEC (requirements) > DESIGN (architecture) > PATTERNS (conventions). Each level has strictly higher authority than the one below. This is the invariant the entire system enforces.

**Authority flow:** When documents conflict, the higher-level document wins. The lower-level document must be amended. A DESIGN decision contradicting a SPEC requirement is a DESIGN bug, never a SPEC bug (unless the user explicitly changes the SPEC).

**Separation of concerns:**
- SPEC answers "what" and "why" -- requirements, constraints, scope boundaries
- DESIGN answers "how" at the architectural level -- modules, packages, interfaces, technology choices
- PATTERNS answers "how" at the code level -- naming, testing patterns, error handling style

**Checkable statements:** Each document contains statements verifiable against source code. A checkable statement is any assertion implying a testable property of the codebase:
- "The system must use a `src/` layout" (SPEC) -> check `src/` directory exists
- "Flat module layout" (DESIGN) -> check no nested subpackages
- "All public functions must have docstrings" (PATTERNS) -> scan public function definitions

Not all statements are checkable. "The hierarchy authority order is non-negotiable" is a process constraint, not a code property. The compliance checker must distinguish between code-checkable and process-only statements.

**Promise contract:** Before code is written, a plan declares what files will change and by how much. After code is written, the system verifies actual changes match the declaration. The promise is stored as TOML (`docs/change_promise.toml`) for human readability and machine parseability. Each task declares files to create/modify/remove, expected line counts, context files, doc sections, reference skills, and dependencies.

**Adoption vs scaffolding:** `prothon new` creates a full project with toolchain. `prothon init` overlays only the documentation-driven workflow onto an existing project without touching code, config, dependencies, or git history. Both create the same doc scaffolds and agent instruction files.

## Mental Models

**Documents as contracts, not documentation.** Traditional docs describe what was built. Prothon docs prescribe what will be built. They are written before code and serve as specifications for AI agents. Think of them as executable requirements.

**Authority as conflict resolution.** The hierarchy exists to answer "who wins?" unambiguously. Without this, agents make arbitrary choices that drift across sessions.

**Compliance as continuous verification.** Compliance checking runs after every task and on demand. It is the feedback loop that detects drift between intent (docs) and reality (code).

**Harmonization as downward propagation.** When SPEC changes, DESIGN may need updating. When DESIGN changes, PATTERNS may need updating. Changes propagate downward, never upward. The doc-harmonizer detects contradictions and proposes amendments but never applies them without user approval.

**Tolerance in verification.** The promise system uses tolerances (+-30% or +-30 lines, whichever is greater) for line count verification. Binary files are excluded. Plans are estimates, not exact predictions. A report passes if it contains no FAIL entries -- SKIP results (e.g. no files declared for a category) do not affect the outcome.

## Edge Cases & Gotchas

- **Implicit requirements.** "The scaffolded toolchain is fixed" implies no configuration mechanism for tool selection should exist. The compliance checker must handle both explicit and implicit requirements.
- **Cross-document dependencies.** A PATTERNS rule like "all public functions must have docstrings" depends on DESIGN defining module boundaries. Changes to DESIGN can invalidate PATTERNS rules without directly contradicting them.
- **Empty documents block downstream.** SPEC must be substantively populated before DESIGN can be written. A stub SPEC with only comments does not count.
- **Partial compliance is normal during development.** The compliance report should distinguish "not yet implemented" from "implemented incorrectly".
- **Scope boundaries matter.** SPEC's "Out of Scope" section is as important as its requirements. Out-of-scope implementations should be flagged.
- **Concurrent document editing.** Two agents must never edit the same document simultaneously. The workflow enforces sequential editing.

## Validation Rules

- SPEC.md, DESIGN.md, and PATTERNS.md must each parse as valid Markdown with expected sections.
- Every requirement in SPEC should be addressable in DESIGN (coverage check).
- Every technology in DESIGN should have a corresponding reference skill.
- No DESIGN statement should contradict any SPEC statement (harmonization invariant).
- No PATTERNS statement should contradict any DESIGN or SPEC statement.
- SPEC may only be modified through the spec-writer agent.
- The doc-harmonizer must never modify a document without user approval.
