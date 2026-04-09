# Implementation Patterns

> **Progressive disclosure:** Per-module API signatures live in `docs/references/` and are loaded as needed via `context_files` entries in `change_promise.toml`. This file focuses on patterns, conventions, and rationale — not inline module signatures.

<!-- Requires: docs/DESIGN.md must be populated first -->

## Code Organization
<!-- Module structure, file naming, directory layout conventions -->
<!-- How the src/ package is organized and why -->

Describe how source files are laid out and named. Cover naming conventions for files, functions, classes, and constants. State the import order policy. Explain which responsibilities belong in which module and why.

## Design Patterns
<!-- Patterns in use (repository, factory, strategy, etc.) and where they apply -->
<!-- Include brief rationale for each pattern choice -->

List the design patterns used in the project, where they apply, and why each was chosen. Focus on *when* to use each pattern and the trade-offs involved. Code examples are limited to function/method signatures — no implementation bodies.

## Error Handling
<!-- How errors are represented, propagated, and reported -->
<!-- Exception hierarchy, error codes, logging conventions -->

Describe the error handling strategy: exception hierarchy, how errors propagate, when to fail fast vs degrade gracefully, and logging conventions. Explain the boundary between library-level errors and CLI-level error presentation.

## Testing Patterns
<!-- Test structure, fixture conventions, what to test vs skip -->
<!-- Naming conventions, assertion style, test data management -->

State the testing philosophy: what to test, what to skip, and how to keep tests fast and lightweight. Cover fixture conventions, fake/stub strategies, and test file organization.
