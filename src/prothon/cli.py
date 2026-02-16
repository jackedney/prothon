"""Prothon CLI — Python project generator with docs-first AI workflow."""

import os
import shutil
import subprocess
from pathlib import Path

import typer
from jinja2 import Environment, BaseLoader

app = typer.Typer(add_completion=False)

COPIER_ANSWERS_TEMPLATE = "{{ _copier_conf.answers_file }}.jinja"


def _template_dir() -> Path:
    """Return the path to the bundled template directory."""
    # When installed as package, template is bundled alongside cli.py
    pkg_template = Path(__file__).parent / "template"
    if pkg_template.is_dir():
        return pkg_template
    # In development, template is at repo root
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "template"


def generate(dest: Path, context: dict) -> None:
    """Generate a project from the template."""
    env = Environment(
        loader=BaseLoader(),
        keep_trailing_newline=True,
    )

    template_dir = _template_dir()
    dest.mkdir(parents=True, exist_ok=True)

    for src_path in sorted(template_dir.rglob("*")):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(template_dir)

        # Skip the copier-specific answers template
        if COPIER_ANSWERS_TEMPLATE in str(rel_path):
            continue

        # Template the path itself (handles {{ module_name }} dirs)
        rendered_rel = env.from_string(str(rel_path)).render(context)
        dest_path = dest / rendered_rel

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.suffix == ".jinja":
            # Render Jinja template and strip .jinja suffix
            dest_path = dest_path.with_suffix("")
            content = src_path.read_text()
            rendered = env.from_string(content).render(context)
            dest_path.write_text(rendered)
        else:
            # Copy as-is
            shutil.copy2(src_path, dest_path)

    # Create symlinks for agent instruction files
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = dest / name
        if not link.exists():
            os.symlink("AGENTS.md", link)

    # Create symlinks for skill directories (.claude/skills, .opencode/skills -> .agents/skills)
    for dir_name in (".claude", ".opencode"):
        parent = dest / dir_name
        parent.mkdir(parents=True, exist_ok=True)
        link = parent / "skills"
        if not link.exists():
            os.symlink(os.path.join("..", ".agents", "skills"), link)

    # Write .copier-answers.yml for copier update support
    _write_copier_answers(dest, context)

    # Initialize git
    subprocess.run(["git", "init"], cwd=dest, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=dest, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit from prothon template"],
        cwd=dest,
        capture_output=True,
        check=True,
    )


def _write_copier_answers(dest: Path, context: dict) -> None:
    """Write .copier-answers.yml for copier update compatibility."""
    lines = [
        "# Changes here will be overwritten by Copier",
        "_src_path: gh:jackedney/prothon",
    ]
    for key in (
        "project_name",
        "module_name",
        "description",
        "author_name",
        "author_email",
        "python_version",
        "license",
    ):
        lines.append(f"{key}: {context[key]}")
    (dest / ".copier-answers.yml").write_text("\n".join(lines) + "\n")


@app.command()
def main(
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
    author_name = typer.prompt("Author name")
    author_email = typer.prompt("Author email")

    python_version = typer.prompt(
        "Python version (3.11/3.12/3.13)", default="3.13"
    )
    while python_version not in ("3.11", "3.12", "3.13"):
        typer.echo("Must be 3.11, 3.12, or 3.13")
        python_version = typer.prompt(
            "Python version (3.11/3.12/3.13)", default="3.13"
        )

    license_choice = typer.prompt("License (MIT/Apache-2.0/None)", default="MIT")
    while license_choice not in ("MIT", "Apache-2.0", "None"):
        typer.echo("Must be MIT, Apache-2.0, or None")
        license_choice = typer.prompt(
            "License (MIT/Apache-2.0/None)", default="MIT"
        )

    context = {
        "project_name": project_name,
        "module_name": module_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "python_version": python_version,
        "license": license_choice,
    }

    generate(dest, context)
    typer.echo(f"\nProject created at {dest}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {dest.name}")
    typer.echo("  uv sync")
    typer.echo("  poe check")
