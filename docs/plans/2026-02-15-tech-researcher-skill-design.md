# Tech Researcher Skill Design

**Goal:** Add a Tech Researcher agent that automatically generates practical SKILL.md reference files for every technology chosen in DESIGN.md, so coding agents have up-to-date library knowledge during implementation.

**Approach:** Custom researcher using Context7 MCP (primary) and web search (fallback). No external CLI dependencies.

---

## Role & Trigger

- **Name:** Tech Researcher
- **Model:** Sonnet 4.5 (autonomous, no interactive Q&A)
- **Trigger:** After DESIGN.md is written, before Patterns Writer
- **Workflow position:** SPEC Writer → Design Writer → **Tech Researcher** → Patterns Writer → ...

## Process

1. **Read DESIGN.md** — Parse the Technology Choices table to extract each package/tool name and its purpose
2. **Research each technology** — For each package:
   - Use Context7 MCP (`resolve-library-id` → `query-docs`) to fetch up-to-date documentation
   - Fall back to web search if Context7 doesn't have the library indexed
3. **Generate SKILL.md** — For each package, write a file to `docs/skills/tech/<package-name>.md` containing:
   - **Quick Start** — minimal setup/import to get going
   - **Common Patterns** — the 3-5 most-used API patterns with examples
   - **Gotchas & Pitfalls** — common mistakes, surprising behavior, version-specific quirks
   - **Idiomatic Usage** — what "good" code looks like with this library
4. **Write summary** — Report which skills were generated and any packages where research was limited

## Output Structure

```
docs/skills/tech/
├── fastapi.md
├── sqlalchemy.md
├── pydantic.md
└── ...
```

## Guards

- Each file should be concise — target 100-200 lines max (practical reference, not exhaustive docs)
- Do NOT include architecture opinions (that's DESIGN.md's job)
- Do NOT include project-specific patterns (that's PATTERNS.md's job)
- Focus purely on "how to use this library well"

## Files to Create & Modify

| Action | File | Change |
|--------|------|--------|
| Create | `template/docs/skills/tech-researcher.md` | New skill definition |
| Modify | `template/docs/skills/design-writer.md` | Update "What Comes Next" to direct to Tech Researcher |
| Modify | `template/AGENTS.md.jinja` | Add Tech Researcher to skills table and workflow |

`docs/skills/tech/` is NOT baked into the template — it gets created at runtime by the agent when it runs, since contents depend on DESIGN.md choices.
