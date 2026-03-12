# Project Specification

## Purpose

Prothon is a CLI tool that scaffolds opinionated Python projects and provides a structured documentation-driven workflow for keeping AI coding assistants aligned with project intent across sessions. It solves two problems: repetitive project setup (by generating a ready-to-use project with a fixed dev toolchain and pre-commit hooks), and AI drift (by establishing a three-level documentation hierarchy that serves as a durable source of truth for AI agents, with automated verification that code matches documented intent). For existing Python projects, prothon can overlay just the documentation-driven workflow without touching the project's existing code, configuration, or toolchain.

## Requirements

### Project Scaffolding

1. The system must scaffold a new Python project from a single CLI command (`prothon new`).
2. The system must prompt the user for: module name, description, author name, author email, Python version, and license.
3. The scaffolded project must use a `src/` layout with a typed package (`py.typed` marker).
4. The scaffolded project must include a fixed dev toolchain: uv (package management), poethepoet (task runner), ruff (linting and formatting), ty (type checking), pytest and hypothesis (testing), mutmut (mutation testing), bandit (security scanning), vulture (dead code detection), and complexipy (complexity analysis).
5. The scaffolded project must include pre-commit hooks that enforce all toolchain checks on every commit.
6. The scaffolded project must include CI workflows for both GitHub Actions and GitLab CI/CD, plus a pre-commit CI workflow, all running the full set of toolchain checks.
7. The scaffolded project must initialize a git repository with an initial commit.
8. The scaffolded project must include agent instruction files that teach AI assistants the documentation hierarchy and development workflow.
9. The scaffolded project must include empty doc scaffolds for SPEC.md, DESIGN.md, and PATTERNS.md.

### Project Adoption

10. The system must adopt an existing Python project into the documentation-driven workflow via a single CLI command (`prothon init`).
11. The command must verify the current directory is a git repository and exit with an error if it is not.
12. The command must verify that `docs/SPEC.md` does not already exist and exit with an error if it does, directing the user to `prothon new` or manual setup.
13. The command must create a `docs/` directory with empty scaffolds for SPEC.md, DESIGN.md, and PATTERNS.md, identical to those created by `prothon new`.
14. The command must create AGENTS.md and symlinks (CLAUDE.md, GEMINI.md, AGENT.md) pointing to AGENTS.md.
15. The command must create a `.agents/skills/` directory for project-specific reference skills.
16. The command must print a summary of created files and suggest running `prothon spec` as the next step.
17. The command must not modify existing source files, dependencies, toolchain, pre-commit hooks, or git history. The command may add CI workflows for semantic versioning.

### Documentation Hierarchy

18. The system must enforce a three-level documentation hierarchy: SPEC.md (requirements), DESIGN.md (architecture), and PATTERNS.md (design patterns and conventions).
19. SPEC.md must have the highest authority. When documents conflict, higher-level documents override lower-level documents.
20. SPEC.md must exist before DESIGN.md can be written. DESIGN.md must exist before PATTERNS.md can be written.
21. SPEC.md must only be modifiable through the spec-writer agent. No other agent may alter it.
22. Each documentation level must have a dedicated interactive agent: spec-writer for SPEC.md, design-writer for DESIGN.md, patterns-writer for PATTERNS.md.
23. Documentation agents must enforce separation of concerns — the spec-writer must refuse to include technology choices, the design-writer must refuse to include code patterns, and so on.
24. The doc-harmonizer must detect conflicts between documentation levels and suggest amendments to the lower-authority document, requiring user approval before making changes.
25. PATTERNS.md must focus on selecting and describing Python design patterns suitable for achieving the architecture defined in DESIGN.md. Pattern rationale and behavioral logic must be expressed in natural language, not code.
26. Code examples in PATTERNS.md must be limited to function and method signatures (name, parameter types, and return types). Implementation logic must not appear in code form.

### Code Execution

27. The system must provide an execute workflow that reads all documentation levels and generates a plan of implementation tasks.
28. Each task in the plan must declare the files to be created, modified, or removed, along with predicted line counts.
29. The user must approve the plan before any code is written.
30. Each task must execute in an isolated agent context with only the files and skills relevant to that task.
31. After each task completes, the system must verify the actual changes against the declared plan, including checking that files exist or were removed as expected and that line counts are within tolerance.
32. The system must run the project's pre-commit hooks after each task to enforce all toolchain quality checks, and must treat hook failures as task failures.
33. If a task fails verification or quality checks, the system must retry up to a configurable number of attempts before reporting failure.

### Compliance Verification

34. The system must provide a compliance checker that verifies source code matches all requirements, design choices, and patterns documented across the three documentation levels.
35. The compliance checker must produce a report listing each checkable item with a PASS, FAIL, or SKIP status and file-and-line evidence. SKIP indicates a check was not applicable (e.g., no files declared for that category).
36. Compliance checking must be mandatory before any implementation work is claimed complete.
37. When compliance failures are found, the system must present them to the user for a decision on whether to update the code or update the documentation.

### Tech Research

38. The system must automatically generate reference skills based on the technology choices made in DESIGN.md.
39. Generated reference skills must be sourced from live documentation, not solely from the AI's training data.
40. Reference skills must cover four categories: library usage, language style conventions, performance patterns, and domain knowledge.
41. Generated reference skills must be stored in the project's local skills directory so they are available to all AI agents working on the project.

### Semantic Versioning

42. The system must automatically bump the project version based on which documentation level changed.
43. Changes to SPEC.md must trigger a major version bump.
44. Changes to DESIGN.md (without SPEC.md changes) must trigger a minor version bump.
45. Changes to PATTERNS.md or source code only (without documentation changes) must trigger a patch version bump.
46. Version bumps must update the version in `pyproject.toml`, `src/<package>/__init__.py`, and create a corresponding git tag.
47. Version bumping must occur automatically in CI without requiring human approval.
48. Scaffolded projects (`prothon new`) must include CI workflows that detect change types and perform version bumps.
49. Adopted projects (`prothon init`) must receive CI workflows that detect change types and perform version bumps.
50. The version bump CI workflow must be included for both GitHub Actions and GitLab CI/CD.

### CLI and Agent Integration

51. All documentation and execution workflows must be invocable via CLI commands (`prothon spec`, `prothon design`, `prothon patterns`, `prothon execute`, `prothon compliance`).
52. The system must support Claude Code, opencode, and Gemini CLI as AI assistants for all agent workflows, with identical behavior and experience across all.
53. The user must be able to select their preferred AI assistant via CLI flag, environment variable, project-level configuration, and global user-level configuration.
54. Built-in skills must be bundled with the package and synced to the active assistant's skill directory on every CLI invocation.
55. The scaffolded project's agent instructions must be assistant-agnostic, using symlinks so that any AI assistant that reads project-level markdown picks up the same instructions.
56. When opencode is the selected assistant, the user must be able to configure a model and provider via the same configuration hierarchy (CLI flag, environment variable, project-level configuration, global user-level configuration). If neither is configured, prothon must invoke opencode without specifying model or provider, deferring to opencode's own defaults.

## Constraints

- The tool must be built in and run via Python.
- The tool must be installable and runnable via `uv`.
- The scaffolded toolchain is fixed and not user-configurable.
- The documentation hierarchy authority order (SPEC > DESIGN > PATTERNS) is non-negotiable.
- No automated agent may modify SPEC.md — only the spec-writer agent may, and only through user interaction.
- No documentation changes may be applied by the doc-harmonizer without user approval.

## Out of Scope

- Support for AI assistants beyond Claude Code, opencode, and Gemini CLI (future consideration).
- Project templates beyond library-style Python packages (planned for future).
- Customization of the scaffolded toolchain (tools are fixed by design).
- Non-Python project scaffolding (planned for future as separate equivalent tools).
- CLI code review tool integration (e.g., Coderabbit, Greptile — planned for future).
- Non-interactive scaffolding mode (e.g., passing all values as flags).
- Remote repository creation (e.g., GitHub/GitLab repo initialization).
- Automatic resolution of compliance failures without user decision.
