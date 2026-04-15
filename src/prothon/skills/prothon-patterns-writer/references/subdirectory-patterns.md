# Subdirectory Patterns Reference

Guidance for splitting PATTERNS.md when it grows too large.

## When to Split

If PATTERNS.md exceeds roughly 300 lines, propose splitting into subdirectory-specific files:

```text
docs/
├── PATTERNS.md              <- shared/global patterns
├── references/
│   ├── modules.md           <- per-module API signatures
│   ├── api.md               <- API-specific reference
│   └── models.md            <- data model reference
├── patterns/
│   ├── api.md               <- API-specific patterns
│   ├── models.md            <- data model patterns
│   └── tests.md             <- testing patterns
```

Each subdirectory file follows the same authority rules (must align with DESIGN.md and SPEC.md). The `docs/references/` directory holds per-module and per-topic signatures; the `docs/patterns/` directory holds expanded pattern detail when PATTERNS.md would be too long.
