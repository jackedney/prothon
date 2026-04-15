# Discovery Detail Reference

Detailed analysis criteria for Wave 0 and Wave 1 during Phase 1 discovery.

## Wave 0 — Documentation Quality (options 1, 5)

First, gather programmatic evidence by running these Python functions:
- `collect_module_metrics(root)` — line counts, function counts, import counts per module
- `collect_pattern_usage(root)` — recurring structural patterns (try/except guards, check-then-act, etc.)
- `collect_cross_module_similarities(root)` — functions with overlapping signatures across modules

Then, using the evidence alongside the full documentation, evaluate:

### DESIGN.md quality
- Do any Key Decisions interact or conflict now that the project has grown?
- Have any modules outgrown their original design boundary? (Use module metrics as evidence.)
- Are there recurring code patterns that suggest an architectural concept DESIGN.md doesn't name? (Use pattern usage data.)
- Are any Technology Choices no longer the best fit given actual usage?

### PATTERNS.md quality
- Are there recurring code shapes across modules that should be codified as a shared convention? (Use pattern usage and cross-module similarity data.)
- Do any documented patterns work for simple cases but break for complex ones?
- What conventions has the codebase adopted organically that PATTERNS.md doesn't document?
- Could any patterns be generalized to cover more cases, reducing special-case logic?
- Are there functions doing essentially the same thing in different modules? (Use similarity data.)

IMPORTANT: SPEC.md is read for context but NEVER modified. Wave 0 only produces DESIGN.md and PATTERNS.md changes.

## Wave 1 — Code Drift (options 2-4, 5)

- **Doc Hierarchy (R24):** Verify `docs/` contains SPEC, DESIGN, and PATTERNS. Check for contradictions using the authority hierarchy (SPEC > DESIGN > PATTERNS).
- **Pattern Compliance (R25, R26):** Verify `docs/PATTERNS.md` uses natural language for rationale and limits code examples to signatures only.
- **Code Health:** Scan `src/` for large modules (> 500 lines) that need splitting. Scan `tests/` for missing test coverage of `src/` modules.

## Findings Presentation Format

Present findings grouped by wave, then by Refactor Wave level, with severity:

```text
Wave 0 — Documentation Quality:
  [DESIGN]
    [D1] commands.py hub pattern has outgrown flat-module design (high)
         Evidence: 423 lines, 8 direct importers, acts as orchestration layer
    [D2] Promise and refactor systems share verification patterns
         but are designed independently (medium)
         Evidence: promise_verify.py and refactor.py both implement check->report loops
  [PATTERNS]
    [P1] File I/O guard pattern used in 6 modules but not codified (medium)
         Evidence: refactor.py:107, compliance.py:42, promise.py:88, ...
    [P2] Error handling convention inconsistent between layers (low)
         Evidence: cli.py catches ProthonError, domain modules raise mixed types

Wave 1 — Code Drift:
  [CODE]
    [C1] cli.py is > 500 lines and should be split (medium)
    [C2] scaffold.py is missing corresponding tests (medium)
```
