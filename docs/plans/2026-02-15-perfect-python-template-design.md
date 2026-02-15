# Perfect Python Template — Design Document

**Date:** 2026-02-15
**Type:** Copier project template

## Purpose

A Copier-based template that generates fully configured, general-purpose Python projects with modern tooling wired together out of the box.

## Template Engine

**Copier** with Jinja2 templating. The repo uses the `_subdirectory: template` pattern — `copier.yml` and docs live at the root, template files live in `template/`.

## Copier Questions

| Question | Type | Default |
|----------|------|---------|
| `project_name` | str | `"my-project"` |
| `module_name` | str | derived from project_name (slugified, underscores) |
| `description` | str | `"A Python project"` |
| `author_name` | str | — |
| `author_email` | str | — |
| `python_version` | choice | `"3.13"` (also: 3.12, 3.11) |
| `license` | choice | `"MIT"` (also: Apache-2.0, None) |

## Tooling Stack

| Tool | Role | Config |
|------|------|--------|
| uv | Package management, venvs, lockfile | `pyproject.toml` |
| Ruff | Linting + formatting | `pyproject.toml [tool.ruff]` |
| ty | Type checking | `pyproject.toml [tool.ty]` |
| pytest | Test runner | `pyproject.toml [tool.pytest]` |
| hypothesis | Property-based testing | dev dependency |
| mutmut | Mutation testing | `pyproject.toml [tool.mutmut]` |
| bandit | Security linting | `pyproject.toml [tool.bandit]` |
| vulture | Dead code detection | `pyproject.toml [tool.vulture]` |
| complexipy | Complexity checking | CLI / pyproject.toml |
| pre-commit | Git hooks | `.pre-commit-config.yaml` |
| Taskfile | Task runner | `Taskfile.yml` |
| GitHub Actions | CI | `.github/workflows/ci.yml` |

## Generated Project Layout

```
<project_name>/
    src/
        <module_name>/
            __init__.py
            py.typed
    tests/
        __init__.py
        conftest.py
        test_placeholder.py
    docs/
    .github/
        workflows/
            ci.yml
    .pre-commit-config.yaml
    .gitignore
    .python-version
    Taskfile.yml
    pyproject.toml
    README.md
    .copier-answers.yml
```

## Component Details

### pyproject.toml

Single source of truth for project metadata, dependencies, and tool config:

- `[project]` — templated name, description, author, requires-python
- `[build-system]` — hatchling
- `[tool.uv]` — dev dependency group: pytest, hypothesis, mutmut, ruff, ty, bandit, vulture, complexipy, pre-commit
- `[tool.ruff]` — target python version, line-length 88, rule selection (I, E, F, W, UP, B, SIM, N)
- `[tool.ty]` — rules warn by default, environment root pointing to `src/`
- `[tool.pytest.ini_options]` — testpaths, pythonpath, strict markers
- `[tool.mutmut]` — paths to mutate
- `[tool.bandit]` — targets `src/`
- `[tool.vulture]` — min confidence, paths

### Taskfile.yml

- `task install` — uv sync
- `task fmt` — ruff format
- `task lint` — ruff check + ty + bandit + vulture + complexipy
- `task security` — bandit alone
- `task test` — pytest
- `task test:mut` — mutmut run
- `task check` — all quality checks (lint + test)

### pre-commit hooks

1. pre-commit-hooks (trailing whitespace, end-of-file-fixer, check-yaml)
2. ruff (lint + format)
3. ty
4. bandit
5. vulture
6. complexipy

### GitHub Actions CI

- Trigger: push and PR to main
- Matrix: python version from template choice
- Steps: install uv, sync deps, ruff check, ty, bandit, vulture, complexipy, pytest
