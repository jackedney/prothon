"""Prothon CLI — command definitions and output formatting."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Annotated

import tomlkit
import tomlkit.exceptions
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from prothon import promise
from prothon.assistant import _BACKENDS, get_backend, launch
from prothon.exceptions import ProthonError
from prothon.project import find_project_root
from prothon.promise import CheckStatus, TaskCheckReport
from prothon.scaffold import generate, init_existing

console = Console()

_agent_choices = ", ".join(sorted(_BACKENDS.keys()))

AgentOption = Annotated[
    str | None,
    typer.Option(
        "--agent",
        "-a",
        envvar="PROTHON_AGENT",
        help=f"AI agent backend ({_agent_choices})",
    ),
]

ModelOption = Annotated[
    str | None,
    typer.Option(
        "--model",
        "-m",
        envvar="PROTHON_MODEL",
        help="Model name passed to the agent backend",
    ),
]

ProviderOption = Annotated[
    str | None,
    typer.Option(
        "--provider",
        "-p",
        envvar="PROTHON_PROVIDER",
        help="Provider name (opencode only)",
    ),
]

app = typer.Typer(
    add_completion=False,
    help="Python project generator with docs-first AI workflow.",
    invoke_without_command=True,
)

promise_app = typer.Typer(help="Manage change promises (plan, check, execute).")
app.add_typer(promise_app, name="promise")


def _require_project_root() -> Path:
    """Find the project root or exit with an error."""
    try:
        return find_project_root()
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


def _require_doc(root: Path, doc_name: str) -> None:
    """Exit with an error if a prerequisite doc file is missing."""
    doc_path = root / "docs" / doc_name
    if not doc_path.is_file():
        typer.echo(
            f"Error: docs/{doc_name} must exist before this command can run",
            err=True,
        )
        raise typer.Exit(1)


def _require_promise_file(root: Path) -> Path:
    """Resolve promise path against project root, or exit if missing."""
    promise_path = root / promise.PROMISE_PATH
    if not promise_path.exists():
        typer.echo(f"No promise file found at {promise_path}")
        raise typer.Exit(1)
    return promise_path


def _read_toml(path: Path) -> dict:
    """Read a TOML file, returning an empty dict on parse error or missing file."""
    if not path.exists():
        return {}
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomlkit.exceptions.TOMLKitError):
        return {}


def _nested_get(doc: dict, *keys: str) -> str | None:
    """Walk *keys* through nested dicts, returning None if not a mapping."""
    current: object = doc
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return str(current) if current is not None else None


def resolve_agent(cli_value: str | None = None) -> str:
    """Resolve agent backend name via 5-level precedence chain.

    Priority: CLI flag > env var > pyproject.toml > global config > default.
    """
    # Level 1: CLI flag (passed explicitly by caller)
    if cli_value:
        return cli_value

    # Level 2: env var (also resolved by Typer into cli_value, but checked
    # explicitly so non-Typer callers honour the precedence chain)
    env_val = os.environ.get("PROTHON_AGENT")
    if env_val:
        return env_val

    # Level 3: pyproject.toml [tool.prothon].agent
    try:
        root = find_project_root()
        val = _nested_get(
            _read_toml(root / "pyproject.toml"), "tool", "prothon", "agent"
        )
        if val:
            return val
    except ProthonError:
        pass  # No project root found — fall through

    # Level 4: global config ~/.config/prothon/config.toml
    raw_xdg = os.environ.get("XDG_CONFIG_HOME")
    xdg = (
        Path(raw_xdg)
        if raw_xdg and Path(raw_xdg).is_absolute()
        else Path.home() / ".config"
    )
    val = _nested_get(_read_toml(xdg / "prothon" / "config.toml"), "agent")
    if val:
        return val

    # Level 5: default
    return "claude-code"


def _resolve_config_value(
    cli_value: str | None,
    env_var: str,
    config_key: str,
) -> str | None:
    """Resolve a config value via 5-level precedence chain."""
    if cli_value:
        return cli_value
    env_val = os.environ.get(env_var)
    if env_val:
        return env_val
    try:
        root = find_project_root()
        val = _nested_get(
            _read_toml(root / "pyproject.toml"), "tool", "prothon", config_key
        )
        if val:
            return val
    except ProthonError:
        pass
    raw_xdg = os.environ.get("XDG_CONFIG_HOME")
    xdg = (
        Path(raw_xdg)
        if raw_xdg and Path(raw_xdg).is_absolute()
        else Path.home() / ".config"
    )
    val = _nested_get(_read_toml(xdg / "prothon" / "config.toml"), config_key)
    if val:
        return val
    return None


def _resolve_model_value(cli_value: str | None) -> str | None:
    """Resolve model name via 5-level precedence chain."""
    return _resolve_config_value(cli_value, "PROTHON_MODEL", "model")


def _resolve_provider_value(cli_value: str | None) -> str | None:
    """Resolve provider name via 5-level precedence chain."""
    return _resolve_config_value(cli_value, "PROTHON_PROVIDER", "provider")


def resolve_model(cli_model: str | None, cli_provider: str | None) -> str | None:
    """Resolve model and provider into opencode's provider/model format.

    Returns None if neither resolves, or raises ProthonError if only one resolves
    or if a qualified model conflicts with an explicit provider.
    """
    model = _resolve_model_value(cli_model)
    provider = _resolve_provider_value(cli_provider)
    if model is None and provider is None:
        return None
    if model is not None and "/" in model:
        if provider is not None:
            model_provider, _ = model.split("/", 1)
            if model_provider != provider:
                raise ProthonError(
                    f"conflicting providers: model '{model}' specifies provider "
                    f"'{model_provider}' but --provider is '{provider}'"
                )
        return model
    if model is not None and provider is not None:
        return f"{provider}/{model}"
    raise ProthonError(
        "--provider requires --model (and vice versa). "
        "Use provider/model format or set both."
    )


def _file_hash(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if unreadable."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


SKILL_DOC_MAP = {
    "prothon-spec-writer": Path("docs/SPEC.md"),
    "prothon-design-writer": Path("docs/DESIGN.md"),
    "prothon-patterns-writer": Path("docs/PATTERNS.md"),
}


def _enforce_commit(skill_name: str, root: Path) -> None:
    """If a doc-writing skill modified a file but didn't commit, do it now."""
    doc_path = SKILL_DOC_MAP.get(skill_name)
    if not doc_path:
        return

    full_path = root / doc_path
    if not full_path.exists():
        return

    from prothon.git import commit_file, is_dirty

    if is_dirty(doc_path, cwd=root):
        typer.echo(f"  Enforcing commit for {doc_path}...")
        msg = f"docs: update {doc_path.name} via {skill_name}"
        commit_file(doc_path, msg, cwd=root)


def _trigger_follow_ups(
    skill_name: str,
    cwd: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> None:
    """Launch follow-up sessions based on the completed skill and file changes."""
    # R24: doc-harmonizer detects conflicts after any doc change
    if skill_name in (
        "prothon-spec-writer",
        "prothon-design-writer",
        "prothon-patterns-writer",
    ):
        typer.echo("\n  Triggering doc-harmonizer...")
        _launch_skill(
            "prothon-doc-harmonizer",
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )

    # R38: Automatically generate tech references after design changes
    if skill_name == "prothon-design-writer":
        typer.echo("  Triggering tech-researcher...")
        _launch_skill(
            "prothon-tech-researcher",
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )

    # R36: Compliance check is mandatory after execution
    if skill_name == "prothon-execute":
        typer.echo("\n  Triggering compliance-checker...")
        _launch_skill(
            "prothon-compliance-checker",
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )


def _launch_skill(
    skill_name: str,
    cwd: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    run_follow_ups: bool = True,
) -> None:
    """Resolve backend, launch skill, handle errors, and enforce lifecycle."""
    spec_path = cwd / "docs" / "SPEC.md"
    guard_spec = skill_name != "prothon-spec-writer"
    spec_hash = _file_hash(spec_path) if guard_spec else None

    try:
        name = resolve_agent(agent)
        backend = get_backend(name)
        resolved_model = resolve_model(model, provider) if name == "opencode" else None
        rc = launch(backend, skill_name, cwd, model=resolved_model)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if guard_spec and _file_hash(spec_path) != spec_hash:
        typer.echo(
            "Warning: docs/SPEC.md was modified outside of 'prothon spec'. "
            "Only the spec-writer should modify SPEC.md.",
            err=True,
        )

    if rc == 0 and run_follow_ups:
        _enforce_commit(skill_name, cwd)
        _trigger_follow_ups(skill_name, cwd, agent, model, provider)

    if rc != 0:
        raise typer.Exit(rc)


# --- Rich rendering helpers ---


def _render_plan(p: promise.Promise) -> Table:
    """Build a Rich table for the promise plan."""
    base = p.metadata.base_commit or "unknown"
    task_word = "task" if len(p.tasks) == 1 else "tasks"

    table = Table(
        title=f"PLAN: {len(p.tasks)} {task_word} (base: {base})",
        show_lines=True,
    )
    table.add_column("#", style="bold", width=3)
    table.add_column("Title", style="bold")
    table.add_column("Files", no_wrap=False)
    table.add_column("Lines", justify="right")
    table.add_column("Deps")

    for i, task in enumerate(p.tasks):
        files_parts: list[str] = []
        if task.files_to_create:
            files_parts.append(f"[green]+[/green] {', '.join(task.files_to_create)}")
        if task.files_to_modify:
            files_parts.append(f"[yellow]~[/yellow] {', '.join(task.files_to_modify)}")
        if task.files_to_remove:
            files_parts.append(f"[red]-[/red] {', '.join(task.files_to_remove)}")
        files_cell = "\n".join(files_parts) if files_parts else "-"

        lines_cell = f"+{task.expected_lines_added} / -{task.expected_lines_removed}"

        deps_cell = (
            ", ".join(str(d) for d in task.dependencies)
            if task.dependencies
            else "none"
        )

        table.add_row(str(i), escape(task.title), files_cell, lines_cell, deps_cell)

    return table


def _render_status(p: promise.Promise) -> Table:
    """Build a Rich table for task completion status."""
    done = sum(1 for t in p.tasks if t.completed)
    table = Table(title=f"Status: {done}/{len(p.tasks)} completed")
    table.add_column("#", style="bold", width=3)
    table.add_column("Status", width=6)
    table.add_column("Title")

    for i, task in enumerate(p.tasks):
        if task.completed:
            status_cell = Text("\u2713", style="green")
        else:
            status_cell = Text("\u2717", style="red")
        table.add_row(str(i), status_cell, escape(task.title))

    return table


def _render_check_report(report: TaskCheckReport) -> Table:
    """Build a Rich table for a task verification report."""
    result_style = "green" if report.passed else "red"
    result_label = "PASS" if report.passed else "DISCREPANCY"

    title = (
        f'Task {report.task_index}: "{escape(report.title)}" \u2014 '
        f"[{result_style}]{result_label}[/{result_style}]"
    )
    table = Table(title=title)
    table.add_column("Check", style="bold")
    table.add_column("Result", width=6)
    table.add_column("Detail")

    _status_styles = {
        CheckStatus.PASSED: ("PASS", "green"),
        CheckStatus.FAILED: ("FAIL", "red"),
        CheckStatus.SKIPPED: ("SKIP", "yellow"),
    }
    for c in report.checks:
        label, style = _status_styles[c.status]
        table.add_row(c.name, Text(label, style=style), c.detail)

    return table


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    """Python project generator with docs-first AI workflow."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def new(
    destination: str = typer.Argument(
        default=".",
        help="Directory to create the project in (defaults to current directory)",
    ),
) -> None:
    """Generate a new Python project with docs-first AI workflow."""
    dest = Path(destination).resolve()
    project_name = dest.name

    module_name = typer.prompt(
        "Module name",
        default=project_name.lower().replace("-", "_").replace(" ", "_"),
    )
    description = typer.prompt("Description", default="A Python project")
    author_name = typer.prompt("Author name", default="")
    author_email = typer.prompt("Author email", default="")
    while author_email and "@" not in author_email:
        typer.echo("Must be a valid email address (e.g. user@example.com)")
        author_email = typer.prompt("Author email", default="")

    python_version = typer.prompt("Python version (3.11/3.12/3.13)", default="3.13")
    while python_version not in ("3.11", "3.12", "3.13"):
        typer.echo("Must be 3.11, 3.12, or 3.13")
        python_version = typer.prompt("Python version (3.11/3.12/3.13)", default="3.13")

    license_choice = typer.prompt("License (MIT/Apache-2.0/None)", default="MIT")
    while license_choice not in ("MIT", "Apache-2.0", "None"):
        typer.echo("Must be MIT, Apache-2.0, or None")
        license_choice = typer.prompt("License (MIT/Apache-2.0/None)", default="MIT")

    data = {
        "project_name": project_name,
        "module_name": module_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "python_version": python_version,
        "license": license_choice,
    }

    generate(dest, data)
    typer.echo(f"\nProject created at {dest}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {dest.name}")
    typer.echo("  uv sync")
    typer.echo("  uvx prothon spec       # Write requirements")
    typer.echo("  uvx prothon design     # Choose architecture")
    typer.echo("  uvx prothon patterns   # Define conventions")


@app.command()
def init() -> None:
    """Adopt an existing project into the docs-first workflow."""
    try:
        created = init_existing()
        for path in created:
            typer.echo(f"  created {path}")
        typer.echo("\nNext step: uvx prothon spec")
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def spec(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise SPEC.md — extract requirements through probing questions."""
    root = _require_project_root()
    _launch_skill("prothon-spec-writer", root, agent, model, provider)


@app.command()
def design(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise DESIGN.md — research technologies and architecture."""
    root = _require_project_root()
    _require_doc(root, "SPEC.md")
    _launch_skill("prothon-design-writer", root, agent, model, provider)


@app.command()
def patterns(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise PATTERNS.md — define code conventions and testing approaches."""
    root = _require_project_root()
    _require_doc(root, "DESIGN.md")
    _launch_skill("prothon-patterns-writer", root, agent, model, provider)


@app.command()
def execute(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Align source code to documentation — plan and implement with subagents."""
    root = _require_project_root()
    _launch_skill("prothon-execute", root, agent, model, provider)


@app.command()
def compliance(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md)."""
    root = _require_project_root()
    _launch_skill("prothon-compliance-checker", root, agent, model, provider)


@app.command()
def refactor(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Perform documentation-driven full-stack refactoring with the refactor agent."""
    root = _require_project_root()
    _require_doc(root, "SPEC.md")
    _require_doc(root, "DESIGN.md")
    _require_doc(root, "PATTERNS.md")
    _launch_skill("prothon-refactor", root, agent, model, provider)


# --- Promise subcommands ---


@promise_app.command("plan")
def promise_plan() -> None:
    """Pretty-print the change promise plan."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    p = promise.load_promise(promise_path)
    console.print(_render_plan(p))


@promise_app.command("status")
def promise_status() -> None:
    """Show completion status of all tasks."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    p = promise.load_promise(promise_path)
    console.print(_render_status(p))


@promise_app.command("check")
def promise_check(
    task_index: int = typer.Argument(help="Zero-based task index to check"),
) -> None:
    """Verify a task's promises against git reality."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    try:
        report = promise.check_task(task_index, path=promise_path)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
    console.print(_render_check_report(report))
    if not report.passed:
        raise typer.Exit(1)


@promise_app.command("complete")
def promise_complete(
    task_index: int = typer.Argument(help="Zero-based task index to mark complete"),
) -> None:
    """Mark a task as completed (attempt count is read from the promise file)."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    try:
        promise.complete_task(task_index, path=promise_path)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"Task {task_index} marked as completed.")


@promise_app.command("record-attempt")
def promise_record_attempt(
    task_index: int = typer.Argument(
        help="Zero-based task index to record attempt for"
    ),
) -> None:
    """Increment the attempt counter for a task."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    try:
        promise.record_attempt(task_index, path=promise_path)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"Attempt recorded for task {task_index}.")


@promise_app.command("cleanup")
def promise_cleanup() -> None:
    """Remove the promise file after all tasks are complete."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    promise.cleanup(promise_path)
    typer.echo("Promise file removed.")
