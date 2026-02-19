"""Prothon CLI — Python project generator with docs-first AI workflow."""

import os
import shutil
import subprocess
from pathlib import Path

import typer
from jinja2 import Environment, BaseLoader

from prothon import promise

app = typer.Typer(
    add_completion=False,
    help="Python project generator with docs-first AI workflow.",
    invoke_without_command=True,
)

promise_app = typer.Typer(help="Manage change promises (plan, check, execute).")
app.add_typer(promise_app, name="promise")

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


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find a prothon project root."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".copier-answers.yml").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _skills_dir() -> Path:
    """Return the path to the bundled skills directory."""
    return Path(__file__).parent / "skills"


def _sync_skills() -> None:
    """Symlink bundled skills into ~/.claude/skills/ so Claude discovers them via /skill-name."""
    bundled = _skills_dir()
    if not bundled.is_dir():
        return
    target = Path.home() / ".claude" / "skills"
    target.mkdir(parents=True, exist_ok=True)
    for skill_dir in bundled.iterdir():
        if not skill_dir.is_dir():
            continue
        dest = target / skill_dir.name
        if dest.is_symlink():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        dest.symlink_to(skill_dir.resolve())


def launch_claude(skill_name: str, cwd: Path) -> None:
    """Launch an interactive Claude Code session that invokes the given skill."""
    if not shutil.which("claude"):
        typer.echo(
            "Error: Claude Code CLI not found.\n"
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        )
        raise typer.Exit(1)
    _sync_skills()
    subprocess.run(
        ["claude", "--dangerously-skip-permissions", f"/{skill_name}"],
        cwd=cwd,
    )


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

    # Create .agents/skills for project-specific reference skills (tech-*, style-*, etc.)
    (dest / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

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
    typer.echo("  uvx prothon spec       # Write requirements")
    typer.echo("  uvx prothon design     # Choose architecture")
    typer.echo("  uvx prothon patterns   # Define conventions")


@app.command()
def spec() -> None:
    """Write or revise SPEC.md — extract requirements through probing questions."""
    root = _require_project_root()
    launch_claude("prothon-spec-writer", root)


@app.command()
def design() -> None:
    """Write or revise DESIGN.md — research technologies and architecture, then generate tech references."""
    root = _require_project_root()
    launch_claude("prothon-design-writer", root)


@app.command()
def patterns() -> None:
    """Write or revise PATTERNS.md — define code conventions and testing approaches."""
    root = _require_project_root()
    launch_claude("prothon-patterns-writer", root)


@app.command()
def execute() -> None:
    """Align source code to documentation — plan and implement with subagents."""
    root = _require_project_root()
    launch_claude("prothon-execute", root)


@app.command()
def compliance() -> None:
    """Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md)."""
    root = _require_project_root()
    launch_claude("prothon-compliance-checker", root)


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
