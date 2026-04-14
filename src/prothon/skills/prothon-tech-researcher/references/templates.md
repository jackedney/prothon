# Skill File Templates

## Technology template

`.agents/skills/tech-{package-name}/SKILL.md`:

```yaml
---
name: tech-{package-name}
description: "[What] Reference guide for {Package Name}. [When] Use for {purpose from DESIGN.md}. [Capabilities] API patterns, common pitfalls, and idiomatic usage."
user-invocable: false
---

# {Package Name}

## Critical

- Before writing implementation, consult `references/` for detailed API specs
- Follow idiomatic patterns provided below

> Purpose: <from DESIGN.md Technology Choices table>
> Docs: <official documentation URL>
> Version researched: <version if known, or "latest" if unspecified>

## Quick Start

<Minimal setup, installation, and import to get going. 5-10 lines max.>

## Common Patterns

<The 3-5 most frequently used API patterns with brief code examples.>
<Each pattern should be a self-contained example a developer can copy.>

## Gotchas & Pitfalls

<Common mistakes, surprising behavior, version-specific quirks.>
<Things that cause bugs or confusion. Be specific and actionable.>

## Idiomatic Usage

<What "good" code looks like with this library.>
<Anti-patterns to avoid and their idiomatic alternatives.>
```

## Codestyle template

`.agents/skills/style-{language}/SKILL.md`:

```yaml
---
name: style-{language}
description: "[What] Code style conventions for {Language}. [When] Use to ensure idiomatic code and consistency. [Capabilities] Naming, module structure, and formatting rules."
user-invocable: false
---

# {Language} Code Style

## Critical

- Enforce project-specific naming conventions strictly
- Consult `references/style-examples.md` for complex layout patterns

> Style guide: <official/de facto guide name and URL>
> Tooling: <linter/formatter from DESIGN.md or CLAUDE.md>

## Naming Conventions

<Variables, functions, classes, modules, constants — with examples.>

## Import & Module Structure

<Import ordering, grouping, module layout conventions.>

## Type Annotations

<When and how to annotate. Level of strictness. Key patterns.>

## Documentation

<Docstring style, when to document, what to include.>

## Formatting Rules

<Line length, indentation, trailing commas, string quotes — anything the formatter enforces.>
<Note which rules are auto-enforced by tooling vs. must be followed manually.>
```

## Optimisation template

`.agents/skills/optim-{topic}/SKILL.md`:

```yaml
---
name: optim-{topic}
description: "[What] Optimisation patterns for {topic}. [When] Apply during implementation to meet performance constraints. [Capabilities] Key principles, measurement strategies, and high-performance patterns."
user-invocable: false
---

# {Topic} Optimisation

## Critical

- Before premature optimisation, consult `references/benchmarks.md`
- Focus on practical measurement over theoretical gains

> Relevance: <why this matters for this project, referencing SPEC constraints>

## Key Principles

<2-3 core principles that guide optimisation decisions in this area.>

## Recommended Patterns

<3-5 practical patterns with code examples.>
<Each should show the naive approach vs. the optimised approach.>

## Data Structure Choices

<Which data structures to prefer and why, with complexity trade-offs.>

## Measurement

<How to profile and measure performance in this area.>
<Specific tools, benchmarking approaches, what metrics to track.>

## Common Pitfalls

<Performance mistakes that are easy to make and hard to spot.>
```

## Domain template

`.agents/skills/domain-{topic}/SKILL.md`:

```yaml
---
name: domain-{topic}
description: "[What] Domain knowledge for {topic}. [When] Consult to ensure correct implementation of business logic. [Capabilities] Core concepts, mental models, and domain-specific pitfalls."
user-invocable: false
---

# {Topic}

## Critical

- Review `references/glossary.md` for project-specific terminology
- Strictly follow the validation rules defined below

> Relevance: <why developers need to understand this to write correct code>

## Core Concepts

<Key terms and definitions. What they mean and how they relate.>
<Use concrete examples, not abstract definitions.>

## Mental Models

<How to think about the domain when making implementation decisions.>
<Analogies or simplified models that guide correct code.>

## Edge Cases & Gotchas

<Domain-specific edge cases that cause bugs if not handled.>
<Things that seem simple but have surprising complexity.>

## Validation Rules

<How to verify that code is handling domain concepts correctly.>
<Test cases or invariants that must hold.>
```

Note: `user-invocable: false` makes all these auto-discoverable reference skills — agents load them when relevant but they don't clutter the `/` command menu.
