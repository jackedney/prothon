"""Scaffolding-specific CLI commands and interactive prompts."""

from __future__ import annotations

from pathlib import Path

import typer

from prothon import scaffold
from prothon.exceptions import ProthonError


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

    scaffold.generate(dest, data)
    typer.echo(f"\nProject created at {dest}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {dest.name}")
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
    except Exception:
        typer.echo("Error: current directory is not a git repository", err=True)
        raise typer.Exit(code=1)

    # R12: Guard: must not already be initialized
    if (root / "docs" / "SPEC.md").exists():
        typer.echo(f"Error: docs/SPEC.md already exists in {root}", err=True)
        raise typer.Exit(code=1)

    data = None
    if not (root / "pyproject.toml").exists():
        data = _collect_project_details()

    try:
        created = scaffold.init_existing(root, data=data)
        for path in created:
            typer.echo(f"  created {path}")
        typer.echo("\nNext step: uvx prothon spec")
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _collect_project_details() -> dict[str, str]:
    """Collect project details interactively using Typer prompts.

    Returns:
        Dict with module_name, description, author_name, author_email,
        python_version, and license.
    """
    return {
        "module_name": typer.prompt("Module name"),
        "description": typer.prompt("Description"),
        "author_name": typer.prompt("Author name"),
        "author_email": typer.prompt("Author email"),
        "python_version": typer.prompt("Python version", default="3.12"),
        "license": typer.prompt("License", default="MIT"),
    }
