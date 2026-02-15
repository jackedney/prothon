# Perfect Python Template — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Copier template that generates fully configured Python projects with uv, ruff, ty, pytest, hypothesis, mutmut, bandit, vulture, complexipy, pre-commit, Taskfile, and GitHub Actions CI.

**Architecture:** A Copier template repo using `_subdirectory: template`. The root contains `copier.yml` and docs. The `template/` directory contains all Jinja2-templated project files. Running `copier copy` prompts for project metadata and generates a ready-to-use Python project.

**Tech Stack:** Copier, Jinja2, uv, ruff, ty, pytest, hypothesis, mutmut, bandit, vulture, complexipy, pre-commit, go-task, GitHub Actions.

---

### Task 1: Create Copier Configuration

**Files:**
- Create: `copier.yml`

**Step 1: Create `copier.yml`**

```yaml
_min_copier_version: "9.0.0"
_subdirectory: template
_templates_suffix: .jinja
_answers_file: .copier-answers.yml

_tasks:
  - "git init"
  - "git add ."
  - 'git commit -m "Initial commit from perfect-python template"'

project_name:
  type: str
  help: What is your project name?
  default: my-project

module_name:
  type: str
  help: What is your Python module name?
  default: "{{ project_name | lower | replace('-', '_') | replace(' ', '_') }}"

description:
  type: str
  help: A short description of your project.
  default: A Python project

author_name:
  type: str
  help: Author name

author_email:
  type: str
  help: Author email

python_version:
  type: str
  help: Minimum Python version
  choices:
    - "3.13"
    - "3.12"
    - "3.11"
  default: "3.13"

license:
  type: str
  help: Project license
  choices:
    - "MIT"
    - "Apache-2.0"
    - "None"
  default: "MIT"
```

**Step 2: Create template directory**

Run: `mkdir -p template`

**Step 3: Commit**

```bash
git add copier.yml
git commit -m "feat: add copier configuration with project questions"
```

---

### Task 2: Create pyproject.toml Template

**Files:**
- Create: `template/pyproject.toml.jinja`

**Step 1: Create `template/pyproject.toml.jinja`**

```toml
[project]
name = "{{ project_name }}"
version = "0.1.0"
description = "{{ description }}"
requires-python = ">={{ python_version }}"
{% if license != 'None' %}
license = "{{ license }}"
{% endif %}
authors = [
    { name = "{{ author_name }}", email = "{{ author_email }}" },
]
readme = "README.md"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/{{ module_name }}"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "hypothesis>=6.0",
    "mutmut>=3.0",
    "ruff>=0.15",
    "ty>=0.0.17",
    "bandit[toml]>=1.9",
    "vulture>=2.14",
    "complexipy>=5.0",
    "pre-commit>=4.0",
]

[tool.ruff]
target-version = "py{{ python_version | replace('.', '') }}"
line-length = 88
src = ["src", "tests"]

[tool.ruff.lint]
select = ["I", "E", "F", "W", "UP", "B", "SIM", "N"]

[tool.ty.environment]
python-version = "{{ python_version }}"
root = ["src"]

[tool.ty.rules]
all = "warn"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
strict = true
xfail_strict = true

[tool.mutmut]
paths_to_mutate = "src/{{ module_name }}/"
tests_dir = "tests/"

[tool.bandit]
targets = ["src"]

[tool.vulture]
paths = ["src"]
min_confidence = 80
```

**Step 2: Commit**

```bash
git add template/pyproject.toml.jinja
git commit -m "feat: add pyproject.toml template with all tool configs"
```

---

### Task 3: Create Source Package Layout

**Files:**
- Create: `template/src/{{ module_name }}/__init__.py.jinja`
- Create: `template/src/{{ module_name }}/py.typed`

**Step 1: Create `template/src/{{ module_name }}/__init__.py.jinja`**

```python
"""{{ description }}"""
```

**Step 2: Create `template/src/{{ module_name }}/py.typed`**

Empty file (marker for PEP 561 typed packages).

**Step 3: Commit**

```bash
git add template/src/
git commit -m "feat: add source package layout template"
```

---

### Task 4: Create Test Layout

**Files:**
- Create: `template/tests/__init__.py`
- Create: `template/tests/conftest.py`
- Create: `template/tests/test_placeholder.py.jinja`

**Step 1: Create `template/tests/__init__.py`**

Empty file.

**Step 2: Create `template/tests/conftest.py`**

```python
"""Shared test fixtures."""
```

**Step 3: Create `template/tests/test_placeholder.py.jinja`**

```python
"""Placeholder test to verify the test suite runs."""

from {{ module_name }} import __doc__


def test_module_has_docstring():
    assert __doc__ is not None
```

**Step 4: Commit**

```bash
git add template/tests/
git commit -m "feat: add test layout template with placeholder test"
```

---

### Task 5: Create pre-commit Configuration

**Files:**
- Create: `template/.pre-commit-config.yaml.jinja`

**Step 1: Create `template/.pre-commit-config.yaml.jinja`**

Note: ty does not have an official pre-commit hook yet — use a `local` hook that runs `ty check`.

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.1
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: ty
        name: ty type checker
        entry: ty check
        language: system
        types: [python]
        pass_filenames: false

  - repo: https://github.com/PyCQA/bandit
    rev: "1.9.3"
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        additional_dependencies: ["bandit[toml]"]

  - repo: https://github.com/jendrikseipp/vulture
    rev: "v2.14"
    hooks:
      - id: vulture

  - repo: https://github.com/rohaquinlop/complexipy-pre-commit
    rev: v5.1.0
    hooks:
      - id: complexipy
        types_or: [python, pyi]
```

**Step 2: Commit**

```bash
git add template/.pre-commit-config.yaml.jinja
git commit -m "feat: add pre-commit config with ruff, ty, bandit, vulture, complexipy"
```

---

### Task 6: Create Taskfile

**Files:**
- Create: `template/Taskfile.yml`

**Step 1: Create `template/Taskfile.yml`**

This file has no Jinja templating needed — it's static.

```yaml
version: "3"

tasks:
  install:
    desc: Install dependencies
    cmds:
      - uv sync

  fmt:
    desc: Format code
    cmds:
      - uv run ruff format src/ tests/

  lint:
    desc: Run all linters
    cmds:
      - uv run ruff check src/ tests/
      - uv run ty check
      - uv run bandit -c pyproject.toml -r src/
      - uv run vulture src/
      - uv run complexipy src/

  security:
    desc: Run security checks only
    cmds:
      - uv run bandit -c pyproject.toml -r src/

  test:
    desc: Run tests
    cmds:
      - uv run pytest

  test:mut:
    desc: Run mutation testing
    cmds:
      - uv run mutmut run

  check:
    desc: Run all quality checks
    deps: [lint]
    cmds:
      - uv run pytest
```

**Step 2: Commit**

```bash
git add template/Taskfile.yml
git commit -m "feat: add Taskfile with lint, fmt, test, check commands"
```

---

### Task 7: Create GitHub Actions CI Workflow

**Files:**
- Create: `template/.github/workflows/ci.yml.jinja`

**Step 1: Create `template/.github/workflows/ci.yml.jinja`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["{{ python_version }}"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python {% raw %}${{ matrix.python-version }}{% endraw %}
        run: uv python install {% raw %}${{ matrix.python-version }}{% endraw %}

      - name: Install dependencies
        run: uv sync

      - name: Ruff check
        run: uv run ruff check src/ tests/

      - name: Ruff format check
        run: uv run ruff format --check src/ tests/

      - name: Type check (ty)
        run: uv run ty check

      - name: Security check (bandit)
        run: uv run bandit -c pyproject.toml -r src/

      - name: Dead code check (vulture)
        run: uv run vulture src/

      - name: Complexity check (complexipy)
        run: uv run complexipy src/

      - name: Run tests
        run: uv run pytest
```

**Step 2: Commit**

```bash
git add template/.github/
git commit -m "feat: add GitHub Actions CI workflow"
```

---

### Task 8: Create Supporting Files

**Files:**
- Create: `template/.gitignore`
- Create: `template/.python-version.jinja`
- Create: `template/README.md.jinja`
- Create: `template/docs/.gitkeep`
- Create: `template/{{ _copier_conf.answers_file }}.jinja`

**Step 1: Create `template/.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
*.egg

# Virtual environments
.venv/

# uv
uv.lock

# Testing
.pytest_cache/
.mutmut-cache/
htmlcov/
.coverage

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

**Step 2: Create `template/.python-version.jinja`**

```
{{ python_version }}
```

**Step 3: Create `template/README.md.jinja`**

```markdown
# {{ project_name }}

{{ description }}

## Setup

```bash
uv sync
```

## Development

```bash
task check    # Run all quality checks
task fmt      # Format code
task lint     # Run linters
task test     # Run tests
task test:mut # Run mutation testing
```
```

**Step 4: Create `template/docs/.gitkeep`**

Empty file.

**Step 5: Create `template/{{ _copier_conf.answers_file }}.jinja`**

```yaml
# Changes here will be overwritten by Copier
{{ _copier_conf.answers_file | to_nice_yaml }}
```

Wait — the standard Copier answers file template is:

```jinja
{{ _copier_answers | to_nice_yaml }}
```

Use that instead.

**Step 6: Commit**

```bash
git add template/.gitignore template/.python-version.jinja template/README.md.jinja template/docs/.gitkeep "template/{{ _copier_conf.answers_file }}.jinja"
git commit -m "feat: add gitignore, python-version, README, docs, and copier answers templates"
```

---

### Task 9: End-to-End Verification

**Step 1: Install copier if not already available**

Run: `uv tool install copier`

**Step 2: Generate a test project from the template**

Run:
```bash
cd /tmp
copier copy /home/jackedney/Dev/perfect-python ./test-project \
  --data project_name=test-project \
  --data module_name=test_project \
  --data description="Test project" \
  --data author_name="Test" \
  --data author_email="test@example.com" \
  --data python_version="3.13" \
  --data license="MIT"
```

**Step 3: Verify the generated project structure**

Run: `find /tmp/test-project -type f | sort`

Expected: all files present (pyproject.toml, Taskfile.yml, .pre-commit-config.yaml, .github/workflows/ci.yml, src/test_project/__init__.py, etc.)

**Step 4: Verify the generated project works**

Run:
```bash
cd /tmp/test-project
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: all commands succeed.

**Step 5: Verify template values were substituted correctly**

Run: `grep -r "test.project\|test_project\|Test project" /tmp/test-project/pyproject.toml`

Expected: project name, module name, and description are correctly substituted.

**Step 6: Clean up**

Run: `rm -rf /tmp/test-project`

**Step 7: Commit any fixes discovered during verification**

If any issues found, fix and commit individually.

---

### Task 10: Final Commit — Tag v1.0.0

**Step 1: Verify clean state**

Run: `git status`

Expected: clean working tree.

**Step 2: Tag**

Run: `git tag v1.0.0`
