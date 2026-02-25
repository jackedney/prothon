---
name: tech-copier
description: Reference guide for Copier -- project templating with native update support
user-invocable: false
---

# Copier

> Purpose: Project templating with native `copier update` support (R1-R9: project scaffolding)
> Docs: https://copier.readthedocs.io/
> Version researched: >=9.0 (latest 9.6.x)

## Quick Start

```python
from copier import run_copy

# Generate project from local template
run_copy("path/to/template", "path/to/destination")

# With pre-filled answers (skip interactive prompts)
run_copy(
    src_path="path/to/template",
    dst_path="./my-project",
    data={"module_name": "mylib", "author": "Jane"},
)
```

Template directory must contain a `copier.yml` (or `copier.yaml`) defining questions and settings.

## Common Patterns

### Python API -- three main functions

```python
from copier import run_copy, run_update, run_recopy

# Initial generation
worker = run_copy(src_path, dst_path, data=answers, defaults=False)

# Update existing project (3-way merge, preserves user edits)
worker = run_update(dst_path, conflict="rej", overwrite=True)

# Full regeneration (discards evolution history)
worker = run_recopy(dst_path)
```

### Key parameters for run_copy

| Parameter | Type | Purpose |
|-----------|------|---------|
| `data` | `dict` | Pre-fill answers, skip prompts for provided keys |
| `defaults` | `bool` | Accept all default values without prompting |
| `overwrite` | `bool` | Overwrite existing files without asking |
| `vcs_ref` | `str` | Git ref (tag/branch/SHA) to use for template |
| `answers_file` | `str` | Path for `.copier-answers.yml` |
| `unsafe` | `bool` | Allow running template tasks (required for post-gen scripts) |
| `cleanup_on_error` | `bool` | Remove destination on failure (default: `True`) |
| `quiet` | `bool` | Suppress output |
| `skip_if_exists` | `list[str]` | Paths to skip if they already exist in destination |
| `exclude` | `list[str]` | Glob patterns to exclude from rendering |
| `pretend` | `bool` | Dry run -- show what would happen without making changes |

### run_update with advanced options

```python
worker = run_update(
    "./my-project",
    overwrite=True,              # Required for updates via API
    defaults=True,               # Use default/previous answers
    vcs_ref="v2.0.0",           # Update to specific template version
    conflict="inline",           # Conflict resolution mode
    context_lines=3,             # Lines of context for diff
    skip_answered=True,          # Skip already-answered questions
    unsafe=True,                 # Allow tasks/migrations
)
```

### copier.yml question definition

```yaml
module_name:
  type: str
  help: "Python module name (snake_case)"

python_version:
  type: str
  help: "Minimum Python version"
  default: "3.12"
  choices:
    - "3.11"
    - "3.12"
    - "3.13"

license:
  type: str
  default: "MIT"
  choices: ["MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause"]
```

### copier.yml settings (underscore-prefixed)

```yaml
_min_copier_version: "9.0.0"
_subdirectory: template
_templates_suffix: .jinja
_answers_file: .copier-answers.yml
_exclude:
    - "*.pyc"
    - "__pycache__"
_skip_if_exists:
    - ".env"
_tasks:
    - "git init"
    - command: "pre-commit install"
      when: "{{ use_precommit }}"
```

### Template variables in files

Files ending in `.jinja` are rendered and the `.jinja` suffix is stripped. Use `{{ variable_name }}` syntax:

```jinja
[project]
name = "{{ module_name }}"
version = "{{ version }}"
authors = [
    { name = "{{ author }}", email = "{{ email }}" }
]
requires-python = ">={{ python_version }}"
```

Directory and file names can also be templated: `{{ module_name }}/`.

### Jinja2 raw blocks for literal braces

```jinja
{% raw %}
- uses: actions/checkout@v4
  with:
    fetch-depth: ${{ github.event.pull_request.commits }}
{% endraw %}
```

Required for files containing literal `{{ }}` syntax (GitHub Actions workflows, Jinja2 templates within the template).

### Accessing answers after copy

```python
worker = run_copy(src_path, dst_path, data=answers)
print(f"Project created with answers: {worker.answers.combined}")
```

## Gotchas & Pitfalls

- **`unsafe=True` is required** to run post-generation tasks defined in `copier.yml`. Without it, tasks are silently skipped.
- **Template updates require a git repo.** `run_update()` reads `.copier-answers.yml` and needs the template's git history for 3-way merge. The template source must be a git repo (not a plain directory) for update to work.
- **`.copier-answers.yml` must be committed.** It records which template version was used. If missing, `run_update()` cannot determine the base for merging.
- **`conflict="rej"`** creates `.rej` files with rejected hunks. `conflict="inline"` inserts Git-style conflict markers. Choose `rej` for programmatic handling.
- **Question `type` matters for validation.** Supported types: `str`, `int`, `float`, `bool`, `yaml`, `json`.
- **`_subdirectory` in `copier.yml`** is needed when template files are in a subdirectory of the repo (common when the repo also contains docs/tests for the template itself).
- **Copier strips `.jinja` suffix after rendering.** A file named `pyproject.toml.jinja` becomes `pyproject.toml`. The template repo cannot contain both `foo.txt` and `foo.txt.jinja` -- they would conflict in the output.

## Idiomatic Usage

**Do:** Keep template logic minimal -- use `copier.yml` conditions to include/exclude files rather than complex Jinja2 logic inside files.

**Do:** Pass `data` for non-interactive usage (testing, CI). Pass `defaults=True` to accept all defaults without prompts.

**Don't:** Call `run_copy()` without catching exceptions -- wrap in try/except for user-friendly error messages, especially for git-related failures.

**Do:** Use `when` conditions in `copier.yml` for conditional questions rather than Jinja2 `{% if %}` blocks in templates.

**Don't:** Rely on `_copier_operation` for behavior changes inside templates -- keep copy and update behavior identical where possible.
