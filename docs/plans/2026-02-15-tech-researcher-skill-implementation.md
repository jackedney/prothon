# Tech Researcher Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Tech Researcher agent skill that auto-generates practical SKILL.md reference files for each technology chosen in DESIGN.md, using Context7 MCP and web search.

**Architecture:** One new skill file, two file modifications. The skill defines an autonomous Sonnet 4.5 agent that reads DESIGN.md, researches each technology via Context7 MCP + web search fallback, and writes concise reference files to `docs/skills/tech/`.

**Tech Stack:** Markdown (all content), Jinja2 (AGENTS.md.jinja only)

---

### Task 1: Create skill — tech-researcher.md

**Files:**
- Create: `template/docs/skills/tech-researcher.md`

**Step 1: Create the file**

```markdown
# Tech Researcher

## Role

You are the Tech Researcher. Your job is to generate practical, up-to-date SKILL.md reference files for every technology chosen in DESIGN.md. You research each package, platform, or tool and produce a concise coding reference that helps developers use it correctly and idiomatically.

## Model

**Sonnet 4.5** — This agent must be invoked with `model: "sonnet"` when using the Task tool.

## Mode

Autonomous. You read DESIGN.md, research each technology, and generate skill files. You do not ask questions — you produce output and report results.

## Prerequisites

- `docs/DESIGN.md` must exist and be populated (not just scaffold comments)
- If DESIGN.md is empty or missing, refuse to proceed and direct the user to the Design Writer (`docs/skills/design-writer.md`)

## Process

1. **Read DESIGN.md** — Parse the Technology Choices section. Extract every package, framework, platform, or tool listed, along with its stated purpose.
2. **Create output directory** — Ensure `docs/skills/tech/` exists.
3. **Research each technology** — For each technology:
   a. Use Context7 MCP (`resolve-library-id` → `query-docs`) to fetch up-to-date documentation and code examples.
   b. If Context7 does not have the library indexed, fall back to web search for official documentation.
   c. If neither source yields useful results, use training knowledge and clearly note the limitation.
4. **Generate skill file** — For each technology, write a file to `docs/skills/tech/<package-name>.md` following the structure below.
5. **Report** — List all generated skill files and flag any technologies where research was limited.

## Skill File Structure

Each generated file must follow this format:

```
# <Package Name>

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

## Guards

- Each skill file MUST be concise — target 100-200 lines max
- Do NOT include architecture opinions (that belongs in DESIGN.md)
- Do NOT include project-specific patterns (that belongs in PATTERNS.md)
- Do NOT include installation/dependency management (the project uses uv)
- Focus purely on "how to use this library well in code"
- If Context7 or web search results are insufficient, state what could not be verified rather than guessing

## Output

A set of skill files in `docs/skills/tech/`, one per technology from DESIGN.md, plus a summary of what was generated.

## What Comes Next

After tech skills are generated, the user should invoke the Patterns Writer (`docs/skills/patterns-writer.md`) to define implementation patterns. The Patterns Writer can reference these tech skills for library-specific guidance.
```

**Step 2: Verify file exists**

Run: `ls -la template/docs/skills/tech-researcher.md`
Expected: File exists with non-zero size

**Step 3: Commit**

```bash
git add template/docs/skills/tech-researcher.md
git commit -m "feat: add tech-researcher skill (Sonnet 4.5)"
```

---

### Task 2: Update design-writer.md — "What Comes Next" section

**Files:**
- Modify: `template/docs/skills/design-writer.md:70-72`

**Step 1: Update the "What Comes Next" section**

Replace the current ending (lines 70-72):

```markdown
## What Comes Next

After DESIGN.md is written, the user should invoke the Patterns Writer (`docs/skills/patterns-writer.md`) to define implementation patterns based on these design choices.
```

With:

```markdown
## What Comes Next

After DESIGN.md is written, the user should invoke the Tech Researcher (`docs/skills/tech-researcher.md`) to generate practical reference skills for each chosen technology. Then invoke the Patterns Writer (`docs/skills/patterns-writer.md`) to define implementation patterns.
```

**Step 2: Verify the change**

Run: `grep -A 2 "What Comes Next" template/docs/skills/design-writer.md`
Expected: Shows the updated text mentioning Tech Researcher

**Step 3: Commit**

```bash
git add template/docs/skills/design-writer.md
git commit -m "feat: update design-writer to reference tech-researcher as next step"
```

---

### Task 3: Update AGENTS.md.jinja — add Tech Researcher to skills table and workflow

**Files:**
- Modify: `template/AGENTS.md.jinja:37-38,59-67`

**Step 1: Add workflow step for tech skill generation**

After the existing step 2 ("Update Docs Top-Down", ending at line 38), insert a new step before "Harmonize":

Between the current "Use the corresponding writer skill..." line and "### 3. Harmonize", add:

```markdown

### 3. Generate Tech Skills

After any DESIGN-level changes, invoke the Tech Researcher to regenerate reference skills for newly chosen technologies.

Invoke with `model: "sonnet"` — see `docs/skills/tech-researcher.md`
```

Then renumber the subsequent steps: Harmonize becomes 4, Implement becomes 5, Verify Compliance becomes 6.

**Step 2: Add Tech Researcher to the Available Skills table**

Insert a new row after the Design Writer row:

```markdown
| Tech Researcher | `docs/skills/tech-researcher.md` | Sonnet 4.5 | Auto-generate reference skills for chosen technologies |
```

**Step 3: Verify changes**

Run: `grep -n "Tech Researcher" template/AGENTS.md.jinja`
Expected: Shows matches in both the workflow section and the skills table

**Step 4: Commit**

```bash
git add template/AGENTS.md.jinja
git commit -m "feat: add tech-researcher to AGENTS.md workflow and skills table"
```

---

### Task 4: Integration test — generate a project and verify

**Step 1: Generate a test project**

Run:
```bash
cd /tmp && copier copy --trust --defaults --vcs-ref HEAD \
  -d project_name=test-project \
  -d module_name=test_project \
  -d description="A test project" \
  -d author_name="Test Author" \
  -d author_email="test@example.com" \
  -d python_version="3.13" \
  -d license="MIT" \
  /home/jackedney/Dev/perfect-python /tmp/test-project
```

**Step 2: Verify tech-researcher.md exists**

Run: `ls -la /tmp/test-project/docs/skills/tech-researcher.md`
Expected: File exists

**Step 3: Verify tech-researcher has Sonnet 4.5 model specified**

Run: `grep "Sonnet 4.5" /tmp/test-project/docs/skills/tech-researcher.md`
Expected: Shows the model specification line

**Step 4: Verify AGENTS.md references Tech Researcher**

Run: `grep "Tech Researcher" /tmp/test-project/AGENTS.md`
Expected: Shows matches in workflow and skills table

**Step 5: Verify design-writer references Tech Researcher**

Run: `grep "Tech Researcher" /tmp/test-project/docs/skills/design-writer.md`
Expected: Shows updated "What Comes Next" text

**Step 6: Verify workflow step numbering**

Run: `grep "^### [0-9]" /tmp/test-project/AGENTS.md`
Expected: Shows steps 1 through 6 in order

**Step 7: Clean up**

Run: `rm -rf /tmp/test-project`
