---
name: tech-copier
description: Reference guide for Copier — project templating with native update support
user-invocable: false
---

# Copier

> Purpose: Project templating with native `copier update` support (R1-R9: project scaffolding)
> Docs: https://copier.readthedocs.io/
> Version researched: >=9.0

## Quick Start

```python
from copier import run_copy

# Generate project from local template
run_copy("path/to/template", "path/to/destination")

# With pre-filled answers
run_copy(
    src_path="path/to/template",
    dst_path="./my-project",
    data={"module_name": "mylib", "author": "Jane"},
)
```

Template directory must contain a `copier.yml` defining questions and settings.

## Common Patterns

### Python API — three main functions

```python
from copier import run_copy, run_update, run_recopy

# Initial generation
worker = run_copy(src_path, dst_path, data=answers, defaults=False)

# Update existing project (3-way merge, preserves user edits)
worker = run_update(dst_path, conflict="rej")

# Full regeneration (discards evolution history)
worker = run_recopy(dst_path)
```

### Key parameters

| Parameter | Type | Purpose |
|-----------|------|---------|
| `data` | `dict` | Pre-fill answers, skip prompts for provided keys |
| `defaults` | `bool` | Accept all default values without prompting |
| `overwrite` | `bool` | Overwrite existing files without asking |
| `vcs_ref` | `str` | Git ref (tag/branch/SHA) to use for template |
| `answers_file` | `str` | Path for `.copier-answers.yml` (default: `.copier-answers.yml`) |
| `unsafe` | `bool` | Allow running template tasks (required for post-gen scripts) |
| `cleanup_on_error` | `bool` | Remove destination on failure (default: `True`) |
| `quiet` | `bool` | Suppress output |

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

### Template variables in files

Files ending in `.jinja` are rendered. Use `{{ variable_name }}` syntax:

```
# {{ module_name }}

{{ description }}
```

Directory and file names can also be templated: `{{ module_name }}/`.

### Global variables available in templates

- `_copier_answers` — current answers dict (excludes secrets)
- `_copier_conf` — configuration metadata
- `_copier_operation` — `"copy"` or `"update"`
- `_folder_name` — root directory name

## Gotchas & Pitfalls

- **`unsafe=True` is required** to run post-generation tasks defined in `copier.yml`. Without it, tasks are silently skipped. This is a security measure — templates from untrusted sources could run arbitrary commands.
- **Template updates require a git repo.** `run_update()` reads `.copier-answers.yml` and needs the template's git history for 3-way merge. Templates must be git repos (not plain directories) for update to work.
- **`.copier-answers.yml` must be committed.** It records which template version was used. If missing, `run_update()` cannot determine the base for merging.
- **Jinja2 `{% raw %}` blocks** are needed for files that contain literal `{{ }}` syntax (e.g., GitHub Actions workflows, Jinja2 templates within the template).
- **`conflict="rej"`** creates `.rej` files with rejected hunks. `conflict="inline"` inserts Git-style conflict markers. Choose `rej` for programmatic handling, `inline` for manual resolution.
- **Question `type` matters for validation.** Use `str`, `int`, `float`, `bool`, `yaml`, or `json`. The `yaml` type with `multiselect: true` enables checkbox-style selection.

## Idiomatic Usage

**Do:** Keep template logic minimal — use `copier.yml` conditions to include/exclude files rather than complex Jinja2 logic inside files.

**Do:** Use `_subdirectory` in `copier.yml` if template files are in a subdirectory of the repo (common when the repo also contains docs/tests for the template itself).

**Don't:** Call `run_copy()` without catching exceptions — wrap in try/except for user-friendly error messages, especially for git-related failures.

**Do:** Pass `data` for non-interactive usage (testing, CI). Pass `defaults=True` to accept all defaults without prompts.
