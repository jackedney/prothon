"""Prothon CLI — command definitions and output formatting."""

from __future__ import annotations

from pathlib import Path

import typer

from prothon import promise
from prothon.assistant import get_backend, launch
from prothon.exceptions import AssistantNotFoundError
from prothon.project import find_project_root
from prothon.scaffold import generate

app = typer.Typer(
    add_completion=False,
    help="Python project generator with docs-first AI workflow.",
    invoke_without_command=True,
)

promise_app = typer.Typer(help="Manage change promises (plan, check, execute).")
app.add_typer(promise_app, name="promise")


def _require_project_root() -> Path:
    """Find the project root or exit with an error."""
    root = find_project_root()
    if root is None:
        typer.echo(
            "Error: Not inside a prothon-generated project.\n"
            "Generate one with: uvx prothon new my-project"
        )
        raise typer.Exit(1)
    return root


def _launch_skill(skill_name: str, cwd: Path) -> None:
    """Resolve the backend, launch the skill, and handle errors."""
    try:
        backend = get_backend()
        launch(backend, skill_name, cwd)
    except AssistantNotFoundError:
        typer.echo(
            "Error: Claude Code CLI not found.\n"
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        )
        raise typer.Exit(1)


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
    _require_project_root()
    if not promise.PROMISE_PATH.exists():
        typer.echo(f"No promise file found at {promise.PROMISE_PATH}")
        raise typer.Exit(1)
    typer.echo(promise.plan())


@promise_app.command("status")
def promise_status() -> None:
    """Show completion status of all tasks."""
    _require_project_root()
    if not promise.PROMISE_PATH.exists():
        typer.echo(f"No promise file found at {promise.PROMISE_PATH}")
        raise typer.Exit(1)
    typer.echo(promise.status())


@promise_app.command("check")
def promise_check(
    task_index: int = typer.Argument(help="Zero-based task index to check"),
) -> None:
    """Verify a task's promises against git reality."""
    _require_project_root()
    if not promise.PROMISE_PATH.exists():
        typer.echo(f"No promise file found at {promise.PROMISE_PATH}")
        raise typer.Exit(1)
    report = promise.check_task(task_index)
    typer.echo(report.format())
    if not report.passed:
        raise typer.Exit(1)


@promise_app.command("complete")
def promise_complete(
    task_index: int = typer.Argument(help="Zero-based task index to mark complete"),
    attempts: int = typer.Argument(default=1, help="Number of attempts taken"),
) -> None:
    """Mark a task as completed and record attempt count."""
    _require_project_root()
    if not promise.PROMISE_PATH.exists():
        typer.echo(f"No promise file found at {promise.PROMISE_PATH}")
        raise typer.Exit(1)
    promise.complete_task(task_index, attempts=attempts)
    suffix = "s" if attempts != 1 else ""
    typer.echo(f"Task {task_index} marked as completed ({attempts} attempt{suffix}).")


@promise_app.command("cleanup")
def promise_cleanup() -> None:
    """Remove the promise file after all tasks are complete."""
    _require_project_root()
    if not promise.PROMISE_PATH.exists():
        typer.echo(f"No promise file found at {promise.PROMISE_PATH}")
        raise typer.Exit(1)
    promise.cleanup()
    typer.echo("Promise file removed.")
