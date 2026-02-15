# Agent & Skill System Design

## Overview

A documentation hierarchy and agent system for the perfect-python Copier template. Every generated project ships with structured documentation, skill files for AI agents, and a mandatory docs-first development workflow.

## Documentation Hierarchy

Three levels of documentation, ordered by authority (highest to lowest):

### 1. SPEC.md — Requirements

- **Contains:** What the project must do. Purpose, requirements, constraints, scope boundaries.
- **Does NOT contain:** Package names, code, design patterns, architecture opinions, interfaces.
- **Authority:** Highest. All other docs must align with SPEC.
- **Change frequency:** Lowest. Only changes when fundamental requirements change.

### 2. DESIGN.md — Architecture & Technology

- **Contains:** Chosen packages/frameworks, system architecture, interfaces, key decisions with rationale.
- **Does NOT contain:** Code snippets, implementation details, design patterns.
- **Authority:** Medium. Must serve SPEC requirements. Overrides PATTERNS when in conflict.
- **Prerequisite:** SPEC.md must exist and be populated.

### 3. PATTERNS.md — Implementation

- **Contains:** Code conventions, design patterns, error handling approaches, testing patterns, module structure.
- **Authority:** Lowest. Must align with DESIGN choices and SPEC requirements.
- **Prerequisite:** DESIGN.md must exist and be populated.
- **Note:** In large projects, may be split into subdirectory-specific PATTERNS.md files to avoid bloat.

### Conflict Resolution

When documents conflict, the higher-level document wins. Lower documents must be amended to match. The doc-harmonizer agent enforces this.

## Agents

Five agents, each defined in a separate skill file under `docs/skills/`:

### spec-writer.md

- **Model:** Default (user's chosen model)
- **Mode:** Interactive
- **Focus:** Deep understanding of user requirements. Asks probing questions, pushes for precision, surfaces unstated assumptions. Does not propose solutions — only crystallizes what the user needs.
- **Prerequisites:** None (first doc in the hierarchy)
- **Process:** Explore existing context → ask clarifying questions one at a time → propose sections → get approval → write SPEC.md
- **Guard:** Refuses to include package names, code snippets, or design opinions

### design-writer.md

- **Model:** Default (user's chosen model)
- **Mode:** Interactive
- **Focus:** Research and decision-making. Takes SPEC requirements and actively researches options — web search, docs lookup, package comparison. Presents trade-offs with evidence. Finds the right tools and architecture to serve each requirement.
- **Prerequisites:** SPEC.md must exist and be non-empty
- **Process:** Read SPEC.md → research options → propose 2-3 alternatives per decision with trade-offs → get approval per section → write DESIGN.md
- **Guard:** Every technology choice must reference a SPEC requirement it serves

### patterns-writer.md

- **Model:** Default (user's chosen model)
- **Mode:** Interactive
- **Focus:** Implementation craft. Given the chosen tools and architecture from DESIGN, figures out the best code patterns. Considers testability, maintainability, error handling. Proposes concrete conventions backed by reasoning.
- **Prerequisites:** DESIGN.md must exist and be non-empty
- **Process:** Read SPEC.md + DESIGN.md → analyze existing code → propose patterns per category → get approval → write PATTERNS.md
- **Guard:** Every pattern must align with a DESIGN choice

### doc-harmonizer.md

- **Model:** Sonnet 4.5
- **Mode:** Autonomous
- **Focus:** Conflict detection and resolution across the doc hierarchy
- **Prerequisites:** At least SPEC.md must exist
- **Process:** Read all docs top-down → identify contradictions → resolve in favor of higher-level doc → propose amendments to lower docs → apply with user confirmation
- **Output:** List of conflicts found and resolutions applied, or "no conflicts"

### compliance-checker.md

- **Model:** Sonnet 4.5
- **Mode:** Autonomous
- **Focus:** Verifying code matches all documentation
- **Prerequisites:** At least one doc and source code in `src/` must exist
- **Process:** Read all docs → scan all source code → compare → report deviations as a checklist with file:line references
- **Output:** Compliance report listing each doc requirement and whether code satisfies it

## Mandatory Development Workflow

All code changes (features, bug fixes, refactors) must follow this process:

```
User request (feature/bugfix/refactor)
    │
    ▼
Identify highest affected doc level
    │
    ├─ SPEC level? ────→ spec-writer → design-writer → patterns-writer
    ├─ DESIGN level? ──→ design-writer → patterns-writer
    ├─ PATTERNS level? → patterns-writer
    └─ Code-only? ─────→ Skip to harmonize
    │
    ▼
Invoke doc-harmonizer (Sonnet 4.5)
    │
    ▼
Implement code changes
    │
    ▼
Invoke compliance-checker (Sonnet 4.5)
    │
    ▼
All clear? → Commit
Not clear? → Fix code or update docs, re-check
```

### Workflow Rules

1. **Docs-first:** Never write code that isn't reflected in at least one doc level.
2. **Top-down cascade:** A SPEC change must propagate through DESIGN and PATTERNS before code.
3. **Strict ordering:** SPEC → DESIGN → PATTERNS. Cannot write a lower doc without the higher one existing.
4. **Harmonize after every doc change:** Run harmonizer after any doc update as a safety net.
5. **Compliance gate:** Work is not complete until the compliance checker passes. Not optional.
6. **Code-only changes still check:** Even pure refactors run the compliance checker.

### What the Workflow Does NOT Do

- Does not enforce via git hooks (too slow, too fragile)
- Does not prevent manual doc editing (humans can edit directly, then harmonize)
- Does not auto-commit (user controls when to commit)

## AGENTS.md Structure

The central orchestrator document, symlinked to CLAUDE.md, GEMINI.md, AGENT.md:

1. **Project Overview** — Name and description (from copier answers)
2. **Documentation Hierarchy** — The three levels and their rules
3. **Mandatory Development Workflow** — The flow and its rules
4. **Available Skills** — Table referencing each skill file
5. **Conventions** — Standard coding conventions from the template tooling

## Template Integration

### New Files

```
template/
├── AGENTS.md.jinja              ← uses {{ project_name }}, {{ description }}
├── docs/
│   ├── SPEC.md                  ← static scaffold with instructions
│   ├── DESIGN.md                ← static scaffold with instructions
│   ├── PATTERNS.md              ← static scaffold with instructions
│   └── skills/
│       ├── spec-writer.md       ← static
│       ├── design-writer.md     ← static
│       ├── patterns-writer.md   ← static
│       ├── doc-harmonizer.md    ← static
│       └── compliance-checker.md ← static
```

### Copier Post-Tasks

```yaml
_tasks:
  - "git init"
  - "ln -s AGENTS.md CLAUDE.md"
  - "ln -s AGENTS.md GEMINI.md"
  - "ln -s AGENTS.md AGENT.md"
  - "git add ."
  - "git commit -m 'Initial commit from perfect-python template'"
```

### Existing Files

All existing template files remain unchanged. This is purely additive.

## Doc Scaffold Content

Each doc ships with section headers and HTML comments explaining what belongs in each section. No project-specific content — just structural guidance for the writing agents.

### SPEC.md Sections
- Purpose, Requirements, Constraints, Out of Scope

### DESIGN.md Sections
- Architecture, Technology Choices, Interfaces, Key Decisions

### PATTERNS.md Sections
- Code Organization, Design Patterns, Error Handling, Testing Patterns
