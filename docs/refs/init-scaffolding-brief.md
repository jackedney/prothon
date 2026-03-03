# Feature Brief: `prothon init` Python Project Scaffolding

## Problem

`prothon init` only creates documentation and agent files (docs/, AGENTS.md, symlinks, .agents/skills/). When run on a non-Python repo (e.g. a site with just HTML/SVG files), it leaves the user with no `pyproject.toml`, no `src/` layout, no tests, no toolchain — and the suggested next step (`prothon spec`) requires `uv sync` which fails because there's no `pyproject.toml`.

There's no path for: "I have an existing repo, it's not a Python project yet, I want to turn it into one with the prothon workflow."

## Desired Behavior

`prothon init` should detect when `pyproject.toml` is missing and offer to scaffold the full Python project structure alongside the docs workflow. When `pyproject.toml` already exists, it behaves as today (docs-only overlay).

### When `pyproject.toml` is missing:

1. Prompt for project details (same as `prothon new`): module name, description, author name/email, Python version, license
2. Generate: `pyproject.toml`, `src/{module}/`, `tests/`, `.pre-commit-config.yaml`, CI workflows, `.gitignore`, `README.md`
3. Must **not overwrite** any existing files — skip files that already exist (e.g. if README.md is already present, keep it)
4. Create docs + agent files as today
5. Do **not** run `git init` or create commits (repo already exists)

### When `pyproject.toml` already exists:

No change — docs-only overlay as today.

## Affected SPEC Requirements

- **Requirement 10**: Currently says "adopt an existing Python project" — should broaden to "adopt an existing project" (may or may not be Python yet)
- **Requirement 17**: Currently says "must not modify existing files, configuration, dependencies, toolchain" — needs nuance: when pyproject.toml is absent, init *creates* the Python structure; it still must not overwrite existing files
- **New requirement**: When pyproject.toml is missing, init must prompt the user and scaffold the Python project structure using the same template as `prothon new`, skipping any files that already exist

## Design Consideration

The implementation should reuse the existing Copier template infrastructure from `prothon new` rather than duplicating file generation logic. The key difference from `new` is: no git init, no initial commit, and skip-existing-files behavior.
