# Technology Choices Rationale

Extended rationale for each technology choice. Summary table in DESIGN.md.

**Typer** — Already in use. Lowest boilerplate for 12 commands across two nesting levels. Type hints drive parameter inference. Rich-formatted help output included. Actively maintained (v0.24.1, Feb 2026). If ever abandoned, migration to raw Click is mechanical since Typer generates Click objects internally.

**uv** — Industry standard for high-performance Python package management. Provides deterministic environments across all project commands, including the execution quality gate.

**poethepoet** — Provides a centralized `check` command that encapsulates the entire quality suite (Ruff, Ty, Pytest, Bandit, Vulture, Complexipy). This ensures the execution agent uses the same standard as CI and human developers.

**Copier** — Template updating via `copier update` with 3-way merge is central to prothon's value proposition. When prothon's template evolves, existing projects pull in changes without losing local modifications. Clean Python API (`run_copy`, `run_update`, `run_recopy`) designed for library embedding. Declarative prompts with types, validation, and conditions. Neither cookiecutter nor custom Jinja2 provides template updating.

**tomlkit** — `change_promise.toml` is a human-authored contract. When prothon programmatically updates fields like `completed` or `attempts`, it must not destroy comments, spacing, or ordering. Only tomlkit preserves these on roundtrip. Rich document construction helpers (`comment()`, `table()`, `aot()`) enable scaffolding well-formatted TOML from scratch. Maintained by the Poetry organization. The 18x parsing slowdown vs tomllib is irrelevant for small config files.

**Rich** — Already installed at zero marginal cost (Typer unconditionally depends on it). Best-in-class table rendering with per-cell styling, colored PASS/FAIL, and column alignment. Using it for promise plans, status, and compliance reports is free. Interactive prompts remain on `typer.prompt()`.

**subprocess for git** — Every git operation prothon needs maps to a single CLI command with a machine-readable output flag (`--numstat`, `--name-only`, `--porcelain`). No operation benefits from in-process git access. Zero dependencies. `--numstat` (critical for promise verification) is trivial via subprocess but problematic with dulwich. List-form arguments with `GIT_TERMINAL_PROMPT=0` provide a minimal attack surface.

**Jinja2** — Already a transitive dependency (Copier depends on it), so adding an explicit pin costs zero additional packages. Used directly in `adoption_templates.py` and `scaffold.py` for rendering AGENTS.md, doc stubs, and CI workflow files during `prothon init` and `prothon new`. `string.Template` lacks conditionals and loop constructs needed for scaffold logic. Mako is a heavier alternative with no advantage given Jinja2 is already present.
