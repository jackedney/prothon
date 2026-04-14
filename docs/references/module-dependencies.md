# Module Dependencies

Inter-module import relationships for the prothon package. Loaded by subagents via `context_files` entries in `change_promise.toml` when modifying module boundaries or understanding call chains.

```text
cli.py
  ├── commands.*
  ├── scaffold_cli.new_project(), init_project()
  ├── assistant._BACKENDS
  └── project.find_project_root()

commands.py
  ├── assistant.get_backend(), launch()
  ├── config.resolve_agent(), resolve_model(), file_hash(), find_init_path(), ...
  ├── git.commit_file(), is_dirty()
  ├── models.PROMISE_PATH
  ├── promise.*, promise_verify.*
  ├── project.find_project_root()
  ├── checks.run_static_checks()
  └── ui.render_check_report(), render_compliance_report(), render_plan(), render_status()

adoption.py
  ├── adoption_templates.* (template loading)
  ├── ast_miner.ASTPatternMiner
  ├── scaffold.get_template_dir()
  └── git.run_git()

checks.*
  └── compliance.CheckResult, CheckStatus, CheckType, ComplianceReport, Requirement

refactor.*
  ├── refactor.models.DriftCategory, Severity, PatternType, DriftFinding, ModuleMetrics, PatternOccurrence, SimilarityGroup
  ├── refactor.metrics.collect_module_metrics(), collect_pattern_usage(), collect_cross_module_similarities()
  ├── refactor.discovery.discover_drift() → checks.check_patterns_doc(), compliance.CheckStatus
  ├── refactor.testability._has_testable_logic(), _is_testable_function(), _is_testable_class(), _is_trivial_function()
  └── refactor.promise_gen.generate_refactor_promise() → models.Task, Metadata, Promise, git.rev_parse_head()

scaffold_cli.py
  └── scaffold.generate()

scaffold_cli.py (init)
  └── adoption.init_existing()

promise.py
  ├── models.Task, Metadata, Promise, PROMISE_PATH
  └── promise_verify.check_task()

promise_verify.py
  ├── compliance.CheckStatus
  ├── exceptions.PromiseError
  ├── git.GitDiffProvider, SubprocessGitDiff
  └── models.Promise, Task

assistant.py
  └── skills.sync_skills(target)

versioning.py
  ├── git.* (for tag operations)
  ├── tomlkit (for version file updates)
  ├── config.read_toml(), config.nested_get(), config.find_init_path()
  └── ui.console

fs.py
  └── (stdlib only: pathlib, tempfile, os)

config.py
  ├── fs.xdg_config_home()
  └── project.find_project_root()

All modules
  ├── project.find_project_root()
  ├── git.*
  ├── exceptions.*
  └── fs.* (where applicable)
```

`cli.py` is the only module that depends on Typer for command definitions. Domain modules (`scaffold.py`, `promise.py`, `versioning.py`, etc.) are plain Python and independently testable without invoking the CLI framework. This separation serves requirement 56 (all workflows invocable via CLI) while keeping domain logic framework-independent.
