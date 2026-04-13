from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from prothon import commands, scaffold_cli, versioning
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
    try:
        return find_project_root()
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _run_session_command(
    cmd: Callable[..., int | None],
    agent: str | None,
    model: str | None,
    provider: str | None,
) -> None:
    root = _require_project_root()
    try:
        result = cmd(root, agent, model, provider)
        if isinstance(result, int) and result != 0:
            raise typer.Exit(result)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _register_session_command(
    app: typer.Typer,
    name: str,
    help_text: str,
    cmd: Callable[..., int | None],
) -> None:
    def _command(
        agent: AgentOption = None,
        model: ModelOption = None,
        provider: ProviderOption = None,
    ) -> None:
        _run_session_command(cmd, agent, model, provider)

    _command.__name__ = name
    _command.__doc__ = help_text
    app.command(name=name)(_command)


def _register_promise_command(
    app: typer.Typer,
    name: str,
    help_text: str,
    cmd: Callable[..., None],
    has_task_index: bool = False,
) -> None:
    if has_task_index:

        def _command(
            task_index: int = typer.Argument(help="Zero-based task index"),
        ) -> None:
            root = _require_project_root()
            try:
                cmd(root, task_index)
            except ProthonError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(1) from exc
    else:

        def _command() -> None:
            root = _require_project_root()
            try:
                cmd(root)
            except ProthonError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(1) from exc

    _command.__name__ = f"promise_{name.replace('-', '_')}"
    _command.__doc__ = help_text
    app.command(name)(_command)


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


_register_session_command(
    app,
    "spec",
    "Write or revise SPEC.md — extract requirements through probing questions.",
    commands.spec_command,
)
_register_session_command(
    app,
    "design",
    "Write or revise DESIGN.md — research technologies and architecture.",
    commands.design_command,
)
_register_session_command(
    app,
    "patterns",
    "Write or revise PATTERNS.md — define code conventions and testing approaches.",
    commands.patterns_command,
)
_register_session_command(
    app,
    "execute",
    "Align source code to documentation — plan and implement with subagents.",
    commands.execute_command,
)
_register_session_command(
    app,
    "compliance",
    "Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md).",
    commands.compliance_command,
)
_register_session_command(
    app,
    "refactor",
    "Perform documentation-driven full-stack refactoring with the refactor agent.",
    commands.refactor_command,
)

_register_promise_command(
    promise_app,
    "plan",
    "Pretty-print the change promise plan.",
    commands.promise_plan_command,
)
_register_promise_command(
    promise_app,
    "status",
    "Show completion status of all tasks.",
    commands.promise_status_command,
)
_register_promise_command(
    promise_app,
    "check",
    "Verify a task's promises against git reality.",
    commands.promise_check_command,
    has_task_index=True,
)
_register_promise_command(
    promise_app,
    "complete",
    "Mark a task as completed (attempt count is read from the promise file).",
    commands.promise_complete_command,
    has_task_index=True,
)
_register_promise_command(
    promise_app,
    "record-attempt",
    "Increment the attempt counter for a task.",
    commands.promise_record_attempt_command,
    has_task_index=True,
)
_register_promise_command(
    promise_app,
    "cleanup",
    "Remove the promise file after all tasks are complete.",
    commands.promise_cleanup_command,
)


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
        versioning.ci_bump_command(root, before_sha, after_sha, dry_run, no_tag)
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
        versioning.ci_detect_command(root, before_sha, after_sha)
    except ProthonError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
