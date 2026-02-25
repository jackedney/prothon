---
name: domain-template-engines
description: Domain knowledge -- project template engine concepts for correct scaffolding implementation
user-invocable: false
---

# Project Template Engines

> Relevance: Prothon uses Copier with Jinja2 templates to scaffold new Python projects and support template evolution via `copier update`. Developers must understand template rendering semantics, the update lifecycle, and template-vs-runtime boundaries to implement scaffolding correctly. (SPEC R1-R9)

## Core Concepts

**Template rendering pipeline:** A template engine takes input data (answers to prompts) and a directory tree of template files, then produces a rendered output directory. The pipeline is: collect answers -> resolve conditions -> render Jinja2 -> strip `.jinja` suffix -> write output. Files without `.jinja` suffix are copied verbatim.

**Copier's three operations:**
- `run_copy` -- initial project generation from a template (one-time)
- `run_update` -- apply template evolution to an existing project using 3-way merge (repeatable)
- `run_recopy` -- full regeneration discarding project history (destructive)

The key differentiator is `run_update`: it compares the old template output, new template output, and the user's current files to produce a merged result that preserves user edits while applying template changes.

**Answers file (`.copier-answers.yml`):** Records which template version and which answers were used for the last copy/update. This file is the source of truth for `run_update`. It must be committed to git. Without it, Copier cannot determine the merge base.

**Template source must be a git repo.** Copier uses git tags/commits to track template versions. `run_update` needs the template's git history to compute diffs between the old and new template versions. A plain directory works for `run_copy` but not `run_update`.

**Post-generation tasks:** Copier can run shell commands after rendering (e.g., `git init`, `uv sync`). Tasks require `unsafe=True` in the Python API. Tasks defined in `copier.yml` under `_tasks` run in the output directory.

## Mental Models

**Templates are programs, not documents.** A template directory is a program that takes data (answers) and produces a project. The program has conditionals (`when` in `copier.yml`, `{% if %}` in Jinja2), loops, and variable substitution. Treat template bugs like code bugs.

**Update is a 3-way merge, not a reapply.** `copier update` does not simply re-render and overwrite. It computes: (1) what the old template produced, (2) what the new template produces, (3) what the user currently has. It then merges (3) with the diff between (1) and (2). User edits in areas the template did not change are preserved.

**Template and runtime are separate concerns.** The template produces files at generation time. Runtime code reads those files. The template should not contain runtime logic, and runtime code should not depend on template internals (like Jinja2 variable names or `copier.yml` structure).

**Answer validation is the template's responsibility.** The template defines what inputs are valid (types, choices, regex patterns). Runtime code should not re-validate template answers -- it should trust that the generated output is well-formed.

**Init scaffolds are inlined, not template-derived.** Per DESIGN.md, `prothon init` inlines markdown headers in `scaffold.py` (3-5 lines each) rather than reading from the Copier template. This avoids coupling init to Copier's internal file layout and ensures template restructuring cannot break init.

## Edge Cases & Gotchas

- **Jinja2 syntax conflicts.** Files containing literal `{{ }}` or `{% %}` (GitHub Actions workflows, Jinja2 templates within the template) must use `{% raw %}...{% endraw %}` blocks. Forgetting this causes Copier to try rendering workflow expressions as Jinja2 variables.
- **Directory names can be templated.** `{{ module_name }}/` becomes the actual directory name. But if the answer contains characters invalid for directory names, the result is broken.
- **`unsafe=True` is required for tasks.** Without it, post-generation tasks (like `git init`) are silently skipped. This is a security feature -- templates from untrusted sources could run arbitrary commands.
- **Empty rendered files.** If a Jinja2 condition excludes all content, the result is an empty file that still gets created. Templates should use `copier.yml` `when` conditions to exclude files entirely rather than rendering them empty.
- **`_subdirectory` for mixed repos.** When the template files live in a subdirectory of a repo that also contains template tests and docs, use `_subdirectory` in `copier.yml` to point Copier at the right directory.
- **Copier strips `.jinja` suffix after rendering.** A file named `pyproject.toml.jinja` becomes `pyproject.toml`. This means the template repo cannot contain both `foo.txt` and `foo.txt.jinja` -- they would conflict in the output.
- **Boolean questions in `copier.yml` default to `False`.** If you want a feature included by default, set `default: true` explicitly.

## Validation Rules

- The template directory must contain a `copier.yml` or `copier.yaml` file.
- All Jinja2 variables referenced in templates must be defined as questions in `copier.yml` or as computed values.
- Files with literal `{{ }}` syntax must be wrapped in `{% raw %}` blocks.
- Post-generation tasks must only run idempotent operations (safe to re-run on `copier update`).
- The `.copier-answers.yml` file must be included in the template's `.gitignore` exclusion (it should be committed by the user, not templated).
- Template rendering must produce valid files -- syntactically correct TOML, YAML, Python, etc.
- All template conditionals (`when`, `{% if %}`) must have test coverage for both branches.
- The template must produce six items from user input: module name, description, author name, email, Python version, license (per SPEC R2).
- Template assets live in `src/prothon/template/` and are included via `[tool.hatch.build.targets.wheel.force-include]` (per DESIGN.md).
