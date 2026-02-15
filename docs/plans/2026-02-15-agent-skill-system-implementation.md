# Agent & Skill System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a documentation hierarchy (SPEC/DESIGN/PATTERNS), five agent skill files, and an orchestrating AGENTS.md to the perfect-python Copier template so every generated project ships with docs-first AI workflow infrastructure.

**Architecture:** Static markdown files for doc scaffolds and skills, one jinja-templated AGENTS.md, symlinks created by copier post-tasks. All files live under `template/` so they're included in generated projects.

**Tech Stack:** Copier (template engine), Markdown (all content), Jinja2 (AGENTS.md only)

---

### Task 1: Create doc scaffold — SPEC.md

**Files:**
- Create: `template/docs/SPEC.md`

**Step 1: Create the file**

```markdown
# Project Specification

## Purpose
<!-- What problem does this project solve? What is its core mission? -->
<!-- Keep this abstract — no mention of specific tools, libraries, or patterns -->

## Requirements
<!-- List each requirement as a clear, testable statement -->
<!-- Example: "The system must authenticate users before granting access" -->
<!-- NOT: "Use JWT tokens for authentication" (that's a DESIGN decision) -->

## Constraints
<!-- Non-negotiable boundaries: performance targets, compatibility, regulations -->

## Out of Scope
<!-- Explicitly list what this project does NOT do -->
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/SPEC.md`
Expected: File exists with non-zero size

**Step 3: Commit**

```bash
git add template/docs/SPEC.md
git commit -m "feat: add SPEC.md scaffold template"
```

---

### Task 2: Create doc scaffold — DESIGN.md

**Files:**
- Create: `template/docs/DESIGN.md`

**Step 1: Create the file**

```markdown
# Design Document

<!-- Requires: docs/SPEC.md must be populated first -->

## Architecture
<!-- High-level system structure. Components and how they connect. -->
<!-- Reference which SPEC requirements drive these architectural choices. -->

## Technology Choices
<!-- Chosen packages/frameworks and WHY they were chosen -->
<!-- For each choice, reference which SPEC requirement it serves -->
<!-- Example: -->
<!-- | Package | Purpose | Serves Requirement | -->
<!-- |---------|---------|-------------------| -->
<!-- | FastAPI  | HTTP API framework | "Must expose REST endpoints" | -->

## Interfaces
<!-- API boundaries, data formats, protocols between components -->
<!-- Define inputs, outputs, and contracts — no implementation details -->

## Key Decisions
<!-- Decisions that required research or trade-off analysis -->
<!-- For each: decision made, alternatives considered, rationale for choice -->
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/DESIGN.md`
Expected: File exists with non-zero size

**Step 3: Commit**

```bash
git add template/docs/DESIGN.md
git commit -m "feat: add DESIGN.md scaffold template"
```

---

### Task 3: Create doc scaffold — PATTERNS.md

**Files:**
- Create: `template/docs/PATTERNS.md`

**Step 1: Create the file**

```markdown
# Implementation Patterns

<!-- Requires: docs/DESIGN.md must be populated first -->

## Code Organization
<!-- Module structure, file naming, directory layout conventions -->
<!-- How the src/ package is organized and why -->

## Design Patterns
<!-- Patterns in use (repository, factory, strategy, etc.) and where they apply -->
<!-- Include brief rationale for each pattern choice -->

## Error Handling
<!-- How errors are represented, propagated, and reported -->
<!-- Exception hierarchy, error codes, logging conventions -->

## Testing Patterns
<!-- Test structure, fixture conventions, what to test vs skip -->
<!-- Naming conventions, assertion style, test data management -->
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/PATTERNS.md`
Expected: File exists with non-zero size

**Step 3: Commit**

```bash
git add template/docs/PATTERNS.md
git commit -m "feat: add PATTERNS.md scaffold template"
```

---

### Task 4: Create skill — spec-writer.md

**Files:**
- Create: `template/docs/skills/spec-writer.md`

**Step 1: Create the file**

```markdown
# Spec Writer

## Role

You are the Spec Writer. Your job is to deeply understand what the user needs and crystallize it into a precise, testable specification. You do NOT propose solutions, choose technologies, or suggest patterns. You extract and clarify requirements.

## Model

Default (user's chosen model)

## Prerequisites

None. SPEC.md is the first document in the hierarchy.

## Focus

- Ask probing questions to uncover the real need behind stated wants
- Push for precision — vague requirements become specific, testable statements
- Surface unstated assumptions the user may not realize they're making
- Distinguish between hard requirements and nice-to-haves
- Identify constraints the user hasn't mentioned (performance, compatibility, scale)

## Process

1. **Explore context** — Read any existing code in `src/`, the README, and any prior docs. Understand what already exists.
2. **Ask clarifying questions** — One at a time. Start broad ("What problem does this solve?") and narrow down ("When you say 'fast', what response time is acceptable?"). Prefer multiple-choice questions when possible.
3. **Propose sections** — Once you understand the domain, draft each SPEC.md section and present it for approval:
   - Purpose (1-3 sentences, no jargon)
   - Requirements (numbered, testable statements)
   - Constraints (non-negotiable boundaries)
   - Out of Scope (explicit exclusions)
4. **Get approval** — Present each section individually. Revise based on feedback before moving on.
5. **Write SPEC.md** — Write the final approved content to `docs/SPEC.md`.

## Guards

You MUST refuse to include any of the following in SPEC.md:
- Package or library names (e.g., "Use FastAPI" belongs in DESIGN.md)
- Code snippets or pseudocode (belongs in PATTERNS.md)
- Design patterns (e.g., "Use repository pattern" belongs in PATTERNS.md)
- Architecture opinions (e.g., "Use microservices" belongs in DESIGN.md)
- Interface definitions (belongs in DESIGN.md)

If the user insists on including these, explain that they belong in DESIGN.md or PATTERNS.md and offer to note them for later.

## Output

A populated `docs/SPEC.md` with all sections filled in using clear, testable language.

## What Comes Next

After SPEC.md is written, the user should invoke the Design Writer (`docs/skills/design-writer.md`) to create DESIGN.md based on these requirements.
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/skills/spec-writer.md`
Expected: File exists

**Step 3: Commit**

```bash
git add template/docs/skills/spec-writer.md
git commit -m "feat: add spec-writer skill"
```

---

### Task 5: Create skill — design-writer.md

**Files:**
- Create: `template/docs/skills/design-writer.md`

**Step 1: Create the file**

```markdown
# Design Writer

## Role

You are the Design Writer. Your job is to research and choose the best technologies, architecture, and interfaces to fulfill the requirements in SPEC.md. You make informed decisions backed by evidence — comparing options, reading documentation, and presenting trade-offs.

## Model

Default (user's chosen model)

## Prerequisites

- `docs/SPEC.md` must exist and be populated (not just scaffold comments)
- If SPEC.md is empty or missing, refuse to proceed and direct the user to the Spec Writer (`docs/skills/spec-writer.md`)

## Focus

- Research actively — use web search, documentation lookups, and package comparisons
- For each decision, present 2-3 alternatives with pros/cons and evidence
- Every technology choice must trace back to a specific SPEC requirement
- Consider the project's constraints (from SPEC) when evaluating options
- Prefer well-maintained, widely-adopted packages over obscure ones
- Think about how choices interact — will package A work well with package B?

## Process

1. **Read SPEC.md** — Understand every requirement and constraint thoroughly.
2. **Identify decisions** — List all technology/architecture decisions that need to be made to fulfill the SPEC.
3. **Research options** — For each decision, research 2-3 viable alternatives. Use web search and documentation to gather current information.
4. **Present trade-offs** — For each decision, present options with:
   - What it is and why it's a candidate
   - Pros and cons relative to the SPEC requirements
   - Your recommendation and why
5. **Get approval** — Present each DESIGN.md section individually. Revise based on feedback.
6. **Write DESIGN.md** — Write the final approved content to `docs/DESIGN.md`.

## Sections to Populate

### Architecture
- High-level component structure
- How components connect and communicate
- Reference which SPEC requirements drive each architectural choice

### Technology Choices
- Table format: Package | Purpose | Serves Requirement | Alternatives Considered
- Rationale for each choice

### Interfaces
- API boundaries and data formats
- Contracts between components
- No implementation details — just the "what", not the "how"

### Key Decisions
- Each decision that required research
- Format: Decision | Alternatives | Rationale

## Guards

You MUST refuse to include any of the following in DESIGN.md:
- Code snippets or implementation details (belongs in PATTERNS.md)
- Design patterns (e.g., "Use factory pattern" belongs in PATTERNS.md)
- Anything that contradicts SPEC.md (SPEC has higher authority)

If a SPEC requirement seems impossible to fulfill with available technology, flag it to the user rather than silently ignoring it.

## Output

A populated `docs/DESIGN.md` with all sections filled in, every choice traced to a SPEC requirement.

## What Comes Next

After DESIGN.md is written, the user should invoke the Patterns Writer (`docs/skills/patterns-writer.md`) to define implementation patterns based on these design choices.
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/skills/design-writer.md`
Expected: File exists

**Step 3: Commit**

```bash
git add template/docs/skills/design-writer.md
git commit -m "feat: add design-writer skill"
```

---

### Task 6: Create skill — patterns-writer.md

**Files:**
- Create: `template/docs/skills/patterns-writer.md`

**Step 1: Create the file**

```markdown
# Patterns Writer

## Role

You are the Patterns Writer. Your job is to define the best code patterns, conventions, and implementation approaches for the project, given the technology choices in DESIGN.md and the requirements in SPEC.md. You focus on implementation craft — testability, maintainability, clarity.

## Model

Default (user's chosen model)

## Prerequisites

- `docs/DESIGN.md` must exist and be populated (not just scaffold comments)
- `docs/SPEC.md` must exist and be populated
- If either is empty or missing, refuse to proceed and direct the user to the appropriate writer skill

## Focus

- Choose patterns that serve the chosen technology stack (from DESIGN.md)
- Prioritize testability — every pattern should make testing easier, not harder
- Prioritize simplicity — use the simplest pattern that solves the problem
- Consider how patterns interact across the codebase
- Include concrete examples showing how each pattern looks in this project's context
- Think about error boundaries and failure modes

## Process

1. **Read SPEC.md and DESIGN.md** — Understand requirements and technology choices.
2. **Analyze existing code** — If code exists in `src/`, study its current patterns.
3. **Propose patterns** — For each PATTERNS.md section, propose conventions with reasoning:
   - Code Organization: module structure, naming, layout
   - Design Patterns: which patterns apply and where
   - Error Handling: how errors flow through the system
   - Testing Patterns: test structure and conventions
4. **Show examples** — For each pattern, show a brief concrete example of what it looks like.
5. **Get approval** — Present each section individually. Revise based on feedback.
6. **Write PATTERNS.md** — Write the final approved content to `docs/PATTERNS.md`.

## Guards

You MUST refuse to include anything that contradicts:
- SPEC.md (highest authority — requirements are non-negotiable)
- DESIGN.md (medium authority — technology choices are already decided)

Every pattern must align with a DESIGN.md choice. If a pattern would work better with a different technology, flag it to the user as a potential DESIGN revision rather than silently deviating.

## Subdirectory Patterns

For large projects, PATTERNS.md may become unwieldy. If the file exceeds roughly 300 lines, propose splitting into subdirectory-specific files:

```
docs/
├── PATTERNS.md              ← shared/global patterns
├── patterns/
│   ├── api.md               ← API-specific patterns
│   ├── models.md            ← data model patterns
│   └── tests.md             ← testing patterns
```

Each subdirectory file follows the same authority rules (must align with DESIGN.md and SPEC.md).

## Output

A populated `docs/PATTERNS.md` with all sections filled in, concrete examples, and clear rationale for each choice.

## What Comes Next

After PATTERNS.md is written, the documentation hierarchy is complete. The user can now implement code. All code changes should be verified against these docs using the Compliance Checker (`docs/skills/compliance-checker.md`).
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/skills/patterns-writer.md`
Expected: File exists

**Step 3: Commit**

```bash
git add template/docs/skills/patterns-writer.md
git commit -m "feat: add patterns-writer skill"
```

---

### Task 7: Create skill — doc-harmonizer.md

**Files:**
- Create: `template/docs/skills/doc-harmonizer.md`

**Step 1: Create the file**

```markdown
# Doc Harmonizer

## Role

You are the Doc Harmonizer. Your job is to detect and resolve conflicts between the documentation hierarchy levels (SPEC.md, DESIGN.md, PATTERNS.md). When documents contradict each other, the higher-level document always wins.

## Model

**Sonnet 4.5** — This agent must be invoked with `model: "sonnet"` when using the Task tool.

## Mode

Autonomous. You read all docs, analyze them, and report findings. You do not ask questions — you propose resolutions and apply them with user confirmation.

## Prerequisites

- At least `docs/SPEC.md` must exist and be populated
- If only SPEC.md exists, report "no conflicts possible — only one doc level populated"

## Authority Hierarchy

1. **SPEC.md** — Highest authority. Never amended by this agent.
2. **DESIGN.md** — Medium authority. Amended only to align with SPEC.md.
3. **PATTERNS.md** — Lowest authority. Amended to align with both SPEC.md and DESIGN.md.

## Process

1. **Read all docs** — Read SPEC.md, DESIGN.md (if exists), and PATTERNS.md (if exists) in full.
2. **Cross-reference top-down** — For each statement in DESIGN.md, verify it does not contradict any SPEC.md requirement. For each statement in PATTERNS.md, verify it does not contradict SPEC.md or DESIGN.md.
3. **Identify conflicts** — List every contradiction found, with:
   - The conflicting statements (quoted, with file and section)
   - Which document has higher authority
   - The proposed resolution (amend the lower doc)
4. **Report** — Present findings in this format:

```
## Harmonization Report

### Conflicts Found: N

#### Conflict 1
- **SPEC.md (Section):** "[quoted statement]"
- **DESIGN.md (Section):** "[contradicting statement]"
- **Resolution:** Amend DESIGN.md to say "[proposed text]"

### No Conflicts
✓ All documents are consistent.
```

5. **Apply with confirmation** — For each conflict, show the proposed edit and ask for user confirmation before applying.

## What Counts as a Conflict

- DESIGN.md chooses a technology that cannot fulfill a SPEC requirement
- PATTERNS.md defines a pattern that contradicts a DESIGN.md interface
- DESIGN.md adds requirements not present in SPEC.md (scope creep)
- PATTERNS.md assumes a technology not chosen in DESIGN.md
- Any lower doc making claims about requirements that differ from SPEC.md

## What Does NOT Count as a Conflict

- Lower docs adding detail that doesn't contradict higher docs
- PATTERNS.md defining conventions not mentioned in DESIGN.md (that's expected)
- DESIGN.md making choices not constrained by SPEC.md (that's its job)

## Output

A harmonization report listing all conflicts and their resolutions, or confirming consistency.
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/skills/doc-harmonizer.md`
Expected: File exists

**Step 3: Commit**

```bash
git add template/docs/skills/doc-harmonizer.md
git commit -m "feat: add doc-harmonizer skill (Sonnet 4.5)"
```

---

### Task 8: Create skill — compliance-checker.md

**Files:**
- Create: `template/docs/skills/compliance-checker.md`

**Step 1: Create the file**

```markdown
# Compliance Checker

## Role

You are the Compliance Checker. Your job is to verify that the project's source code faithfully implements what is described in the documentation hierarchy (SPEC.md, DESIGN.md, PATTERNS.md). You scan code and report deviations.

## Model

**Sonnet 4.5** — This agent must be invoked with `model: "sonnet"` when using the Task tool.

## Mode

Autonomous. You read docs, scan code, and produce a compliance report. You do not make changes — you report deviations for the developer to address.

## Prerequisites

- At least one doc (SPEC.md, DESIGN.md, or PATTERNS.md) must be populated
- Source code must exist in `src/`
- If no code exists yet, report "no code to check"

## Process

1. **Read all docs** — Read SPEC.md, DESIGN.md, and PATTERNS.md in full. Extract all checkable statements.
2. **Scan source code** — Read all files in `src/` and `tests/`. Understand the current implementation.
3. **Cross-reference** — For each doc statement, determine whether the code satisfies it.
4. **Report** — Produce a compliance report in this format:

```
## Compliance Report

### SPEC.md Compliance

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | "Must authenticate users" | ✓ PASS | `src/auth/login.py:23` implements auth flow |
| 2 | "Must log all API calls" | ✗ FAIL | No logging found in `src/api/` |

### DESIGN.md Compliance

| # | Design Choice | Status | Evidence |
|---|---------------|--------|----------|
| 1 | "Use FastAPI for HTTP" | ✓ PASS | `src/api/app.py:1` imports FastAPI |
| 2 | "PostgreSQL for storage" | ✗ FAIL | `src/db/` uses SQLite instead |

### PATTERNS.md Compliance

| # | Pattern | Status | Evidence |
|---|---------|--------|----------|
| 1 | "Repository pattern for data access" | ✓ PASS | `src/repos/` follows pattern |
| 2 | "All errors inherit AppError" | ✗ FAIL | `src/api/errors.py:15` uses bare Exception |

### Summary
- SPEC: 8/10 requirements met
- DESIGN: 5/5 choices implemented
- PATTERNS: 3/4 patterns followed
- **Overall: 16/19 (84%)**

### Action Items
1. Add API call logging to satisfy SPEC requirement #2
2. Migrate from SQLite to PostgreSQL per DESIGN choice #2
3. Update error class at `src/api/errors.py:15` to inherit AppError per PATTERNS #2
```

## Checking Rules

### SPEC.md Requirements
- Each requirement should be testable — look for code that demonstrates the capability
- A requirement is PASS if the code clearly implements it
- A requirement is FAIL if no code addresses it or code contradicts it
- A requirement is PARTIAL if some but not all aspects are implemented

### DESIGN.md Choices
- Check that chosen packages are actually imported and used
- Check that interfaces match what DESIGN.md describes
- Check that architecture matches the described component structure

### PATTERNS.md Conventions
- Check that code follows the defined patterns
- Check naming conventions, module structure, error handling
- Check test structure matches testing patterns

## Output

A compliance report with pass/fail status for every checkable statement, file:line evidence, and a prioritized list of action items for failures.
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/skills/compliance-checker.md`
Expected: File exists

**Step 3: Commit**

```bash
git add template/docs/skills/compliance-checker.md
git commit -m "feat: add compliance-checker skill (Sonnet 4.5)"
```

---

### Task 9: Create AGENTS.md.jinja

**Files:**
- Create: `template/AGENTS.md.jinja`

**Step 1: Create the file**

```jinja
# {{ project_name }}

{{ description }}

## Documentation Hierarchy

This project uses a three-level documentation hierarchy. Documents are listed in order of authority — higher documents override lower ones when in conflict.

| Level | Document | Contains | Authority |
|-------|----------|----------|-----------|
| 1 | `docs/SPEC.md` | Requirements, constraints, scope | Highest |
| 2 | `docs/DESIGN.md` | Architecture, packages, interfaces | Medium |
| 3 | `docs/PATTERNS.md` | Code patterns, conventions, testing | Lowest |

**Rules:**
- SPEC.md must exist before DESIGN.md can be written
- DESIGN.md must exist before PATTERNS.md can be written
- When documents conflict, the higher-level document wins and lower documents must be amended

## Mandatory Development Workflow

All code changes — features, bug fixes, refactors — MUST follow this workflow:

### 1. Identify the Highest Affected Doc Level

- Does this change affect **requirements**? → Start at SPEC
- Does this change affect **architecture or packages**? → Start at DESIGN
- Does this change affect **code patterns**? → Start at PATTERNS
- Is this a **code-only change** with no doc impact? → Skip to step 3

### 2. Update Docs Top-Down

Starting from the highest affected level, update each document down through the hierarchy:

- SPEC-level change → update SPEC.md, then DESIGN.md, then PATTERNS.md
- DESIGN-level change → update DESIGN.md, then PATTERNS.md
- PATTERNS-level change → update PATTERNS.md only

Use the corresponding writer skill for each level (see Available Skills below).

### 3. Harmonize

After any doc changes, invoke the Doc Harmonizer to check for conflicts between doc levels.

Invoke with `model: "sonnet"` — see `docs/skills/doc-harmonizer.md`

### 4. Implement

Write the code changes.

### 5. Verify Compliance

Before considering work complete, invoke the Compliance Checker to verify code matches all docs.

Invoke with `model: "sonnet"` — see `docs/skills/compliance-checker.md`

If the compliance check reports failures, fix the code or update docs and re-check.

## Available Skills

| Skill | File | Model | Purpose |
|-------|------|-------|---------|
| Spec Writer | `docs/skills/spec-writer.md` | Default | Interactively write/update SPEC.md — deep requirement understanding |
| Design Writer | `docs/skills/design-writer.md` | Default | Interactively write/update DESIGN.md — research and decision-making |
| Patterns Writer | `docs/skills/patterns-writer.md` | Default | Interactively write/update PATTERNS.md — implementation craft |
| Doc Harmonizer | `docs/skills/doc-harmonizer.md` | Sonnet 4.5 | Check and resolve conflicts between doc levels |
| Compliance Checker | `docs/skills/compliance-checker.md` | Sonnet 4.5 | Verify code matches all documentation |

## Conventions

- **Package manager:** uv
- **Task runner:** task (go-task)
- **Linting:** ruff (linting + formatting)
- **Type checking:** ty
- **Testing:** pytest + hypothesis
- **Security:** bandit
- **Dead code:** vulture
- **Complexity:** complexipy
- **Pre-commit:** hooks enforce all checks on every commit

Run `task check` before committing to verify all quality checks pass.
```

**Step 2: Verify file exists**

Run: `ls -la template/AGENTS.md.jinja`
Expected: File exists

**Step 3: Commit**

```bash
git add template/AGENTS.md.jinja
git commit -m "feat: add AGENTS.md template with workflow and skill references"
```

---

### Task 10: Update copier.yml — add symlink tasks

**Files:**
- Modify: `copier.yml:6-9`

**Step 1: Update _tasks in copier.yml**

Replace the existing `_tasks` block:

```yaml
_tasks:
  - "git init"
  - "git add ."
  - 'git commit -m "Initial commit from perfect-python template"'
```

With:

```yaml
_tasks:
  - "git init"
  - "ln -s AGENTS.md CLAUDE.md"
  - "ln -s AGENTS.md GEMINI.md"
  - "ln -s AGENTS.md AGENT.md"
  - "git add ."
  - 'git commit -m "Initial commit from perfect-python template"'
```

**Step 2: Verify the change**

Run: `grep -A 7 '_tasks' copier.yml`
Expected: Shows all 6 tasks including the 3 symlink commands

**Step 3: Commit**

```bash
git add copier.yml
git commit -m "feat: add AGENTS.md symlinks to copier post-tasks"
```

---

### Task 11: Remove template/docs/.gitkeep

**Files:**
- Delete: `template/docs/.gitkeep`

The `docs/` directory now contains real files (SPEC.md, DESIGN.md, PATTERNS.md, skills/) so the `.gitkeep` placeholder is no longer needed.

**Step 1: Remove the file**

Run: `rm template/docs/.gitkeep`

**Step 2: Verify removal**

Run: `ls template/docs/`
Expected: Shows SPEC.md, DESIGN.md, PATTERNS.md, skills/ — no .gitkeep

**Step 3: Commit**

```bash
git rm template/docs/.gitkeep
git commit -m "chore: remove docs/.gitkeep (replaced by real doc files)"
```

---

### Task 12: Integration test — generate a project and verify

**Step 1: Install copier if needed**

Run: `uv tool install copier`

**Step 2: Generate a test project**

Run:
```bash
cd /tmp && copier copy --defaults \
  -d project_name=test-project \
  -d module_name=test_project \
  -d description="A test project" \
  -d author_name="Test Author" \
  -d author_email="test@example.com" \
  -d python_version="3.13" \
  -d license="MIT" \
  /home/jackedney/Dev/perfect-python /tmp/test-project
```

**Step 3: Verify file structure**

Run: `find /tmp/test-project -name "*.md" -o -name "CLAUDE.md" -o -name "GEMINI.md" -o -name "AGENT.md" | sort`

Expected:
```
/tmp/test-project/AGENT.md
/tmp/test-project/AGENTS.md
/tmp/test-project/CLAUDE.md
/tmp/test-project/GEMINI.md
/tmp/test-project/README.md
/tmp/test-project/docs/DESIGN.md
/tmp/test-project/docs/PATTERNS.md
/tmp/test-project/docs/SPEC.md
/tmp/test-project/docs/skills/compliance-checker.md
/tmp/test-project/docs/skills/design-writer.md
/tmp/test-project/docs/skills/doc-harmonizer.md
/tmp/test-project/docs/skills/patterns-writer.md
/tmp/test-project/docs/skills/spec-writer.md
```

**Step 4: Verify symlinks**

Run: `ls -la /tmp/test-project/CLAUDE.md /tmp/test-project/GEMINI.md /tmp/test-project/AGENT.md`

Expected: All three are symlinks pointing to AGENTS.md

**Step 5: Verify AGENTS.md has templated values**

Run: `head -5 /tmp/test-project/AGENTS.md`

Expected:
```
# test-project

A test project
```

**Step 6: Verify doc scaffolds have instructions (not empty)**

Run: `wc -l /tmp/test-project/docs/SPEC.md /tmp/test-project/docs/DESIGN.md /tmp/test-project/docs/PATTERNS.md`

Expected: Each file has >5 lines

**Step 7: Verify skills have Sonnet 4.5 model specified**

Run: `grep -l "Sonnet 4.5" /tmp/test-project/docs/skills/*.md`

Expected: doc-harmonizer.md and compliance-checker.md

**Step 8: Clean up**

Run: `rm -rf /tmp/test-project`
