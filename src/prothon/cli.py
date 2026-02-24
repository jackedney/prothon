"""Prothon CLI — command definitions and output formatting."""

from __future__ import annotations

import os
from pathlib import Path

import tomlkit
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from prothon import promise
from prothon.assistant import get_backend, launch
from prothon.exceptions import ProthonError
from prothon.promise import CheckStatus, TaskCheckReport
from prothon.project import find_project_root
from prothon.scaffold import generate, init_existing

console = Console()

_state: dict[str, str | None] = {"assistant": None}

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
        raise typer.Exit(1)


def _require_promise_file(root: Path) -> Path:
    """Resolve promise path against project root, or exit if missing."""
    promise_path = root / promise.PROMISE_PATH
    if not promise_path.exists():
        typer.echo(f"No promise file found at {promise_path}")
        raise typer.Exit(1)
    return promise_path


def resolve_assistant() -> str:
    """Resolve assistant backend name via 5-level precedence chain.

    Priority: CLI flag > env var > pyproject.toml > global config > default.
    Levels 1-2 are handled by Typer (--assistant flag + PROTHON_ASSISTANT envvar).
    """
    # Levels 1-2: CLI flag / env var (already resolved by Typer into _state)
    if _state["assistant"]:
        return _state["assistant"]

    # Level 3: pyproject.toml [tool.prothon].assistant
    try:
        root = find_project_root()
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            doc = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
            val = doc.get("tool", {}).get("prothon", {}).get("assistant")
            if val:
                return str(val)
    except ProthonError:
        pass  # No project root found — fall through

    # Level 4: global config ~/.config/prothon/config.toml
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    global_config = xdg / "prothon" / "config.toml"
    if global_config.exists():
        doc = tomlkit.parse(global_config.read_text(encoding="utf-8"))
        val = doc.get("assistant")
        if val:
            return str(val)

    # Level 5: default
    return "claude-code"


def _launch_skill(skill_name: str, cwd: Path) -> None:
    """Resolve the backend, launch the skill, and handle errors."""
    try:
        name = resolve_assistant()
        backend = get_backend(name)
        rc = launch(backend, skill_name, cwd)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


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

    table = Table(
        title=f'Task {report.task_index}: "{escape(report.title)}" \u2014 [{result_style}]{result_label}[/{result_style}]',
    )
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
def callback(
    ctx: typer.Context,
    assistant: str | None = typer.Option(
        None,
        "--assistant",
        "-a",
        envvar="PROTHON_ASSISTANT",
        help="AI assistant backend (claude-code, opencode)",
    ),
) -> None:
    """Python project generator with docs-first AI workflow."""
    _state["assistant"] = assistant
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
        raise typer.Exit(code=1)


@app.command()
def spec() -> None:
    """Write or revise SPEC.md — extract requirements through probing questions."""
    root = _require_project_root()
    _launch_skill("prothon-spec-writer", root)


@app.command()
def design() -> None:
    """Write or revise DESIGN.md — research technologies and architecture, then generate tech references."""
    root = _require_project_root()
    _launch_skill("prothon-design-writer", root)


@app.command()
def patterns() -> None:
    """Write or revise PATTERNS.md — define code conventions and testing approaches."""
    root = _require_project_root()
    _launch_skill("prothon-patterns-writer", root)


@app.command()
def execute() -> None:
    """Align source code to documentation — plan and implement with subagents."""
    root = _require_project_root()
    _launch_skill("prothon-execute", root)


@app.command()
def compliance() -> None:
    """Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md)."""
    root = _require_project_root()
    _launch_skill("prothon-compliance-checker", root)


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
        raise typer.Exit(1)
    console.print(_render_check_report(report))
    if not report.passed:
        raise typer.Exit(1)


@promise_app.command("complete")
def promise_complete(
    task_index: int = typer.Argument(help="Zero-based task index to mark complete"),
    attempts: int = typer.Argument(default=1, help="Number of attempts taken"),
) -> None:
    """Mark a task as completed and record attempt count."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    try:
        promise.complete_task(task_index, attempts=attempts, path=promise_path)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    suffix = "s" if attempts != 1 else ""
    typer.echo(f"Task {task_index} marked as completed ({attempts} attempt{suffix}).")


@promise_app.command("cleanup")
def promise_cleanup() -> None:
    """Remove the promise file after all tasks are complete."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    promise.cleanup(promise_path)
    typer.echo("Promise file removed.")
