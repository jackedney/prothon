---
name: domain-doc-driven-dev
description: Domain knowledge — documentation-driven development concepts for correct implementation
user-invocable: false
---

# Documentation-Driven Development

> Relevance: Prothon's core value proposition is a three-level documentation hierarchy that keeps AI agents aligned. Developers must understand how authority flows between documents and why the constraints exist to implement compliance checking, doc harmonization, and agent workflows correctly.

## Core Concepts

**Three-level hierarchy:** SPEC (requirements) > DESIGN (architecture) > PATTERNS (conventions). Each level has strictly higher authority than the one below. This is not a suggestion — it is the invariant that the entire system enforces.

**Authority flow:** When documents conflict, the higher-level document wins. The lower-level document must be amended. A DESIGN decision that contradicts a SPEC requirement is a DESIGN bug, never a SPEC bug (unless the user explicitly changes the SPEC).

**Separation of concerns:**
- SPEC answers "what" and "why" — requirements, constraints, scope boundaries
- DESIGN answers "how" at the architectural level — modules, packages, interfaces, technology choices
- PATTERNS answers "how" at the code level — naming conventions, testing patterns, error handling style

**Checkable statements:** Each document contains statements that can be verified against source code. A checkable statement is any assertion that implies a testable property of the codebase. Examples:
- "The system must use a `src/` layout" (SPEC) -> check that `src/` directory exists
- "The CLI module depends on Typer" (DESIGN) -> check imports in `cli.py`
- "All public functions must have docstrings" (PATTERNS) -> scan public function definitions
- "Flat module layout with all domain modules at one level" (DESIGN) -> check no nested subpackages

Not all statements are checkable. "The documentation hierarchy authority order is non-negotiable" is a constraint on the process, not the code. The compliance checker must distinguish between code-checkable and process-only statements.

**Promise contract:** Before code is written, a plan declares what files will change and by how much. After code is written, the system verifies actual changes match the declaration. This prevents scope creep and enables task-level accountability. The promise is stored as TOML so it can be both human-readable and machine-parseable.

**Doc-driven workflow sequence:**
1. Write SPEC (requirements) via interactive spec-writer session
2. Write DESIGN (architecture) via interactive design-writer session
3. Write PATTERNS (conventions) via interactive patterns-writer session
4. Generate reference skills via tech-researcher (automated)
5. Execute implementation via execute workflow (planned + verified)
6. Verify compliance (automated quality gate)

Each step depends on the previous steps being complete. Skipping steps produces incomplete context for downstream agents.

## Mental Models

**Documents as contracts, not documentation.** Traditional docs describe what was built. Prothon docs prescribe what will be built. They are written before code and serve as the specification for AI agents. Think of them as executable requirements.

**Authority as conflict resolution.** The hierarchy exists to answer "who wins?" unambiguously. When an AI agent encounters contradictory guidance, it follows the higher-authority document. Without this, agents make arbitrary choices that drift across sessions.

**Compliance as continuous verification.** Compliance checking is not a one-time gate. It runs after every task and can be run on demand. It is the feedback loop that detects drift between intent (docs) and reality (code).

**Harmonization as downward propagation.** When SPEC changes, DESIGN may need updating. When DESIGN changes, PATTERNS may need updating. Changes propagate downward, never upward. The doc-harmonizer detects when a lower document contradicts a higher one and proposes amendments — but never applies them without user approval.

**Tolerance in verification.** The promise system uses tolerances (+-30% or +-30 lines, whichever is greater) for line count verification. This reflects the reality that plans are estimates, not exact predictions. The tolerance is generous enough to accommodate normal implementation variation but tight enough to catch scope creep or missing implementations.

## Edge Cases & Gotchas

- **Implicit requirements.** SPEC may imply constraints that are not explicitly stated. Example: "The scaffolded toolchain is fixed" implies that no configuration mechanism for tool selection should exist. The compliance checker must handle both explicit and implicit requirements.
- **Cross-document dependencies.** A PATTERNS rule like "all public functions must have docstrings" depends on DESIGN defining what "public" means (module boundaries, `__all__`). Changes to DESIGN can invalidate PATTERNS rules without directly contradicting them.
- **Circular authority appears possible but isn't.** "SPEC says use Python" and "DESIGN says use Rust" is a DESIGN bug. But "SPEC says use Python" and "PATTERNS says use `type: ignore` liberally" might feel like a SPEC-level concern — it is not. PATTERNS governs code conventions, and SPEC governs requirements. The test is: does this statement constrain what the system does (SPEC) or how the code is written (PATTERNS)?
- **Empty documents block downstream.** SPEC must exist and be populated before DESIGN can be written. A stub SPEC with only comments does not count. The tech-researcher must verify documents are substantively populated before generating skills.
- **Partial compliance is normal during development.** Not all requirements are implemented at once. The compliance report should distinguish "not yet implemented" (no evidence found) from "implemented incorrectly" (evidence found but wrong).
- **Scope boundaries matter.** SPEC's "Out of Scope" section is as important as its requirements. If something is out of scope, it should not appear in DESIGN or PATTERNS. The compliance checker should flag out-of-scope implementations.
- **Document ordering within a level.** Section ordering within each document is conventional, not enforced. But agents expect certain sections (e.g., "Technology Choices" in DESIGN) to extract structured information. Renaming or restructuring sections can break downstream tools.
- **Concurrent document editing.** Two agents should never edit the same document simultaneously. The workflow enforces sequential editing (spec-writer, then design-writer, then patterns-writer). But if a user manually edits a doc while an agent is running, conflicts can arise.

## Validation Rules

- SPEC.md, DESIGN.md, and PATTERNS.md must each parse as valid Markdown with expected section structure.
- Every requirement in SPEC should be addressable in DESIGN (coverage check).
- Every technology in DESIGN should have a corresponding reference skill (tech-researcher coverage).
- No DESIGN statement should contradict any SPEC statement (harmonization invariant).
- No PATTERNS statement should contradict any DESIGN or SPEC statement.
- The compliance report must cover every checkable statement across all three documents.
- SPEC must be non-empty before DESIGN is writable. DESIGN must be non-empty before PATTERNS is writable.
- The doc-harmonizer must never modify a document without user approval.
- SPEC may only be modified through the spec-writer agent — no other agent or automated process may alter it.
- Compliance report entries must include file:line evidence for PASS results and absence-of-evidence reasoning for FAIL results.
