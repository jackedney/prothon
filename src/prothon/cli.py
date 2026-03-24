from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prothon import commands, scaffold_cli
from prothon.assistant import _BACKENDS
from prothon.exceptions import ProthonError
from prothon.project import find_project_root


_agent_choices = ", ".join(sorted(_BACKENDS.keys()))

AgentOption = Annotated[
    str | None,
    typer.Option(
        "--agent",
        "-a",
        help=f"Assistant backend to launch. Choices: {_agent_choices}",
        envvar="PROTHON_AGENT",
    ),
]

ModelOption = Annotated[
    str | None,
    typer.Option(
        "--model",
        "-m",
        help="Model to use (opencode only). Can be provider/model.",
        envvar="PROTHON_MODEL",
    ),
]

ProviderOption = Annotated[
    str | None,
    typer.Option(
        "--provider",
        "-p",
        help="Provider to use (opencode only).",
        envvar="PROTHON_PROVIDER",
    ),
]

app = typer.Typer(
    name="prothon",
    help="Docs-first AI coding workflow for Python projects.",
    no_args_is_help=True,
    add_completion=False,
)

promise_app = typer.Typer(
    name="promise",
    help="Manage the change promise contract (execution plan).",
    no_args_is_help=True,
)

ci_app = typer.Typer(
    name="ci",
    help="Continuous Integration helpers for versioning and change detection.",
    no_args_is_help=True,
)

app.add_typer(promise_app)
app.add_typer(ci_app)


def _require_project_root() -> Path:
    """Find and return the project root or exit with error."""
    try:
        return find_project_root()
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


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
    scaffold_cli.new_project(destination)


@app.command()
def init() -> None:
    """Adopt an existing project into the docs-first workflow."""
    scaffold_cli.init_project()


@app.command()
def spec(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise SPEC.md — extract requirements through probing questions."""
    root = _require_project_root()
    try:
        rc = commands.spec_command(root, agent, model, provider)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command()
def design(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise DESIGN.md — research technologies and architecture."""
    root = _require_project_root()
    try:
        rc = commands.design_command(root, agent, model, provider)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command()
def patterns(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise PATTERNS.md — define code conventions and testing approaches."""
    root = _require_project_root()
    try:
        rc = commands.patterns_command(root, agent, model, provider)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command()
def execute(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Align source code to documentation — plan and implement with subagents."""
    root = _require_project_root()
    try:
        rc = commands.execute_command(root, agent, model, provider)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command()
def compliance(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md)."""
    root = _require_project_root()
    try:
        commands.compliance_command(root, agent, model, provider)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command()
def refactor(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Perform documentation-driven full-stack refactoring with the refactor agent."""
    root = _require_project_root()
    try:
        rc = commands.refactor_command(root, agent, model, provider)
        if rc != 0:
            raise typer.Exit(rc)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


# --- Promise subcommands ---


@promise_app.command("plan")
def promise_plan() -> None:
    """Pretty-print the change promise plan."""
    root = _require_project_root()
    try:
        commands.promise_plan_command(root)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@promise_app.command("status")
def promise_status() -> None:
    """Show completion status of all tasks."""
    root = _require_project_root()
    try:
        commands.promise_status_command(root)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@promise_app.command("check")
def promise_check(
    task_index: int = typer.Argument(help="Zero-based task index to check"),
) -> None:
    """Verify a task's promises against git reality."""
    root = _require_project_root()
    try:
        commands.promise_check_command(root, task_index)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@promise_app.command("complete")
def promise_complete(
    task_index: int = typer.Argument(help="Zero-based task index to mark complete"),
) -> None:
    """Mark a task as completed (attempt count is read from the promise file)."""
    root = _require_project_root()
    try:
        commands.promise_complete_command(root, task_index)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@promise_app.command("record-attempt")
def promise_record_attempt(
    task_index: int = typer.Argument(help="Zero-based task index to record"),
) -> None:
    """Increment the attempt counter for a task."""
    root = _require_project_root()
    try:
        commands.promise_record_attempt_command(root, task_index)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@promise_app.command("cleanup")
def promise_cleanup() -> None:
    """Remove the promise file after all tasks are complete."""
    root = _require_project_root()
    try:
        commands.promise_cleanup_command(root)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


# --- CI subcommands ---


@ci_app.command("bump")
def ci_bump(
    before_sha: Annotated[
        str, typer.Option("--before-sha", help="Git SHA to diff from")
    ],
    after_sha: Annotated[
        str, typer.Option("--after-sha", help="Git SHA to diff to")
    ] = "HEAD",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Don't perform file updates or tagging")
    ] = False,
    no_tag: Annotated[
        bool, typer.Option("--no-tag", help="Don't create a git tag")
    ] = False,
) -> None:
    """Bump the project version based on changed files since before_sha."""
    root = _require_project_root()
    try:
        commands.ci_bump_command(root, before_sha, after_sha, dry_run, no_tag)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@ci_app.command("detect")
def ci_detect(
    before_sha: Annotated[
        str, typer.Option("--before-sha", help="Git SHA to diff from")
    ],
    after_sha: Annotated[
        str, typer.Option("--after-sha", help="Git SHA to diff to")
    ] = "HEAD",
) -> None:
    """Detect the version bump type based on changed files since before_sha."""
    root = _require_project_root()
    try:
        commands.ci_detect_command(root, before_sha, after_sha)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
