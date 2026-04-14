"""Scaffolding-specific CLI commands and interactive prompts."""

from __future__ import annotations

from pathlib import Path

import typer

from prothon import adoption, scaffold
from prothon.exceptions import GitError, ProthonError


def _prompt_email(field: str = "Author email", default: str = "") -> str:
    value = typer.prompt(field, default=default)
    while value and "@" not in value:
        typer.echo("Must be a valid email address (e.g. user@example.com)")
        value = typer.prompt(field, default=default)
    return value


def _prompt_choice(field: str, choices: tuple[str, ...], default: str) -> str:
    value = typer.prompt(field, default=default)
    while value not in choices:
        typer.echo(f"Must be {', '.join(choices)}")
        value = typer.prompt(field, default=default)
    return value


def new_project(destination: str = ".") -> None:
    """Interactively collect project details and generate a new project."""
    dest = Path(destination).resolve()
    project_name = dest.name

    module_name = typer.prompt(
        "Module name",
        default=project_name.lower().replace("-", "_").replace(" ", "_"),
    )
    description = typer.prompt("Description", default="A Python project")
    author_name = typer.prompt("Author name", default="")
    author_email = _prompt_email()

    python_version = _prompt_choice(
        "Python version (3.11/3.12/3.13)", ("3.11", "3.12", "3.13"), "3.13"
    )
    license_choice = _prompt_choice(
        "License (MIT/Apache-2.0/None)", ("MIT", "Apache-2.0", "None"), "MIT"
    )

    data = {
        "project_name": project_name,
        "module_name": module_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "python_version": python_version,
        "license": license_choice,
    }

    scaffold.generate(dest, data)
    typer.echo(f"\nProject created at {dest}")
    typer.echo("Next steps:")
    if not dest.samefile(Path.cwd()):
        typer.echo(f"  cd {dest}")
    typer.echo("  uv sync")
    typer.echo("  uvx prothon spec       # Write requirements")
    typer.echo("  uvx prothon design     # Choose architecture")
    typer.echo("  uvx prothon patterns   # Define conventions")


def init_project(cwd: Path | None = None) -> None:
    """Adopt an existing project, prompting for details if pyproject.toml is missing."""
    from prothon.git import run_git

    root = cwd if cwd else Path.cwd()

    # R11: Verify git repository before anything else
    try:
        run_git("rev-parse", "--is-inside-work-tree", cwd=root)
    except GitError:
        typer.echo("Error: current directory is not a git repository", err=True)
        raise typer.Exit(code=1)
    except OSError:
        typer.echo("Error: git is not installed or not found on PATH", err=True)
        raise typer.Exit(code=1)

    # R12: Guard: must not already be initialized
    if (root / "docs" / "SPEC.md").exists():
        typer.echo(f"Error: docs/SPEC.md already exists in {root}", err=True)
        raise typer.Exit(code=1)

    data = None
    if not (root / "pyproject.toml").exists():
        data = _collect_project_details()

    try:
        created = adoption.init_existing(root, data=data)
        for path in created:
            typer.echo(f"  created {path}")
        typer.echo("\nNext step: uvx prothon spec")
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _collect_project_details() -> dict[str, str]:
    """Collect project details interactively using Typer prompts."""
    module_name = typer.prompt("Module name")
    description = typer.prompt("Description")
    author_name = typer.prompt("Author name")

    author_email = _prompt_email()
    python_version = _prompt_choice(
        "Python version (3.11/3.12/3.13)", ("3.11", "3.12", "3.13"), "3.13"
    )
    license_choice = _prompt_choice(
        "License (MIT/Apache-2.0/None)", ("MIT", "Apache-2.0", "None"), "MIT"
    )

    return {
        "module_name": module_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "python_version": python_version,
        "license": license_choice,
    }
