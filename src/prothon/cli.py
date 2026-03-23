"""Prothon CLI — command definitions and output formatting."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from prothon import promise, promise_verify, versioning
from prothon.models import PROMISE_PATH
from prothon.assistant import _BACKENDS, get_backend, launch
from prothon.compliance import run_static_checks
from prothon.config import (
    file_hash,
    find_init_path,
    nested_get,
    read_toml,
    resolve_agent,
    resolve_model,
)
from prothon.exceptions import GitError, ProthonError
from prothon.project import find_project_root
from prothon import scaffold_cli
from prothon.ui import (
    console,
    render_check_report,
    render_compliance_report,
    render_plan,
    render_status,
)

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

ci_app = typer.Typer(help="CI automation (version bumping, detection).")
app.add_typer(ci_app, name="ci")


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
    promise_path = root / PROMISE_PATH
    if not promise_path.exists():
        typer.echo(f"No promise file found at {promise_path}")
        raise typer.Exit(1)
    return promise_path


class Skill(StrEnum):
    """Canonical skill names used by the CLI."""

    SPEC_WRITER = "prothon-spec-writer"
    DESIGN_WRITER = "prothon-design-writer"
    PATTERNS_WRITER = "prothon-patterns-writer"
    EXECUTE = "prothon-execute"
    COMPLIANCE = "prothon-compliance-checker"
    DOC_HARMONIZER = "prothon-doc-harmonizer"
    TECH_RESEARCHER = "prothon-tech-researcher"
    REFACTOR = "prothon-refactor"


SKILL_DOC_MAP = {
    Skill.SPEC_WRITER: Path("docs/SPEC.md"),
    Skill.DESIGN_WRITER: Path("docs/DESIGN.md"),
    Skill.PATTERNS_WRITER: Path("docs/PATTERNS.md"),
}


def _enforce_commit(skill_name: str, root: Path) -> None:
    """If a doc-writing skill modified a file but didn't commit, do it now."""
    try:
        s = Skill(skill_name)
    except ValueError:
        return

    doc_path = SKILL_DOC_MAP.get(s)
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
    # R24: doc-harmonizer detects conflicts after any doc change.
    # design-writer and patterns-writer already spawn the harmonizer as a
    # subagent inside their skill flow (and the harmonizer conditionally
    # triggers tech-researcher).  Only spec-writer lacks an internal
    # harmonizer step, so the CLI triggers it here.
    if skill_name == Skill.SPEC_WRITER:
        typer.echo("\n  Triggering doc-harmonizer...")
        _launch_skill(
            Skill.DOC_HARMONIZER,
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )

    # R36 compliance is satisfied by the agent's always-on quality gate
    # (CLAUDE.md step 6) which runs compliance as a subagent inside the
    # execute session.  A second CLI-triggered session would be redundant.


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
    guard_spec = skill_name != Skill.SPEC_WRITER
    spec_hash = file_hash(spec_path) if guard_spec else None

    try:
        name = resolve_agent(agent)
        backend = get_backend(name)
        resolved_model = resolve_model(model, provider) if name == "opencode" else None
        rc = launch(backend, skill_name, cwd, model=resolved_model)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if guard_spec and file_hash(spec_path) != spec_hash:
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
    _launch_skill(Skill.SPEC_WRITER, root, agent, model, provider)


@app.command()
def design(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise DESIGN.md — research technologies and architecture."""
    root = _require_project_root()
    _require_doc(root, "SPEC.md")
    _launch_skill(Skill.DESIGN_WRITER, root, agent, model, provider)


@app.command()
def patterns(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Write or revise PATTERNS.md — define code conventions and testing approaches."""
    root = _require_project_root()
    _require_doc(root, "DESIGN.md")
    _launch_skill(Skill.PATTERNS_WRITER, root, agent, model, provider)


@app.command()
def execute(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Align source code to documentation — plan and implement with subagents."""
    root = _require_project_root()
    _launch_skill(Skill.EXECUTE, root, agent, model, provider)


@app.command()
def compliance(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
) -> None:
    """Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md)."""
    root = _require_project_root()

    # Step 1: Deterministic Static Analysis
    report = run_static_checks(root)

    # Step 2: Semantic Analysis (LLM)
    # Ensure any previous semantic results are cleared
    prothon_dir = root / ".prothon"
    prothon_dir.mkdir(parents=True, exist_ok=True)
    results_path = prothon_dir / "compliance_semantic.json"
    if results_path.exists():
        results_path.unlink()

    typer.echo("Launching semantic compliance checks (LLM)...")
    try:
        _launch_skill(Skill.COMPLIANCE, root, agent, model, provider)
    except ProthonError as exc:
        typer.echo(f"Warning: Semantic checks failed to launch: {exc}")

    # Step 3: Merge and display unified report
    if results_path.exists():
        try:
            with open(results_path, encoding="utf-8") as f:
                findings = json.load(f)
            report.add_from_dicts(findings)
        except (OSError, json.JSONDecodeError) as exc:
            typer.echo(f"Warning: Failed to load semantic compliance results: {exc}")
    else:
        typer.echo(
            "Warning: No semantic results found. The assistant session might have "
            "exited without producing a report or was cancelled."
        )

    console.print("\n", render_compliance_report(report))
    typer.echo("\n" + report.format_summary())


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
    _launch_skill(Skill.REFACTOR, root, agent, model, provider)


# --- Promise subcommands ---


@promise_app.command("plan")
def promise_plan() -> None:
    """Pretty-print the change promise plan."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    p = promise.load_promise(promise_path)
    console.print(render_plan(p))


@promise_app.command("status")
def promise_status() -> None:
    """Show completion status of all tasks."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    p = promise.load_promise(promise_path)
    console.print(render_status(p))


@promise_app.command("check")
def promise_check(
    task_index: int = typer.Argument(help="Zero-based task index to check"),
) -> None:
    """Verify a task's promises against git reality."""
    root = _require_project_root()
    promise_path = _require_promise_file(root)
    try:
        report = promise_verify.check_task(task_index, path=promise_path)
    except ProthonError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
    console.print(render_check_report(report))
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
        bool, typer.Option("--dry-run", help="Don't actually write changes")
    ] = False,
    no_tag: Annotated[
        bool, typer.Option("--no-tag", help="Don't create a git tag")
    ] = False,
) -> None:
    """Bump the project version based on changed files since before_sha.

    Idempotent: if the current version already matches the expected bump,
    the command exits successfully without making changes.
    """
    root = _require_project_root()
    pyproject_path = root / "pyproject.toml"

    # Read current pyproject.toml (CWD)
    doc = read_toml(pyproject_path)
    if not doc:
        typer.echo("Error: Could not read pyproject.toml", err=True)
        raise typer.Exit(1)

    # Check auto_version
    auto_version = nested_get(doc, "tool", "prothon", "ci", "auto_version")
    if auto_version is not None and str(auto_version).lower() in ("false", "0", "no"):
        typer.echo("Automatic versioning is disabled in pyproject.toml")
        return

    # Detect bump type
    bump_type = versioning.detect_bump_type(before_sha, after_sha, cwd=root)
    if not bump_type:
        typer.echo("No version bump needed (no relevant files changed).")
        return

    # Get current version in the branch
    branch_version = nested_get(doc, "project", "version")
    if not branch_version:
        typer.echo("Error: [project] version not found in pyproject.toml", err=True)
        raise typer.Exit(1)

    # Read base version from before_sha
    from prothon.git import run_git

    import tomlkit
    import tomlkit.exceptions

    try:
        base_toml_content = run_git("show", f"{before_sha}:pyproject.toml", cwd=root)
        base_doc = tomlkit.parse(base_toml_content)
        base_version = nested_get(base_doc, "project", "version")
    except (
        GitError,
        FileNotFoundError,
        tomlkit.exceptions.TOMLKitError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        typer.echo(f"Warning: Could not read pyproject.toml from {before_sha}: {exc}")
        base_version = None

    if not base_version:
        typer.echo(f"Falling back to branch version {branch_version} as base")
        base_version = branch_version

    # Compute expected new version
    bump_fn = getattr(versioning, f"bump_{bump_type}")
    expected_version = bump_fn(base_version)

    if branch_version == expected_version:
        typer.echo(f"Version already at {expected_version}, skipping.")
        return

    typer.echo(f"Detected {bump_type} bump: {base_version} -> {expected_version}")

    if dry_run:
        typer.echo("Dry run: Skipping file updates and tagging.")
        return

    # Update files
    versioning.update_pyproject_version(pyproject_path, expected_version)

    # Find __init__.py
    project_name = nested_get(doc, "project", "name")
    if not project_name:
        typer.echo("Error: [project] name not found in pyproject.toml", err=True)
        raise typer.Exit(1)

    module_name = project_name.replace("-", "_")
    init_path = find_init_path(root, project_name, module_name)

    if init_path:
        versioning.update_init_version(init_path, expected_version)
        typer.echo(f"Updated {init_path.relative_to(root)}")
    else:
        typer.echo(
            f"Warning: Could not find __init__.py in src/{module_name} "
            f"or src/{project_name}"
        )

    # Create tag
    if not no_tag:
        try:
            versioning.create_tag(expected_version, cwd=root)
            typer.echo(f"Created tag v{expected_version}")
        except ProthonError as exc:
            typer.echo(f"Warning: Tag creation failed: {exc}", err=True)


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
    bump_type = versioning.detect_bump_type(before_sha, after_sha, cwd=root)
    if bump_type:
        typer.echo(bump_type)
    else:
        typer.echo("none")


if __name__ == "__main__":
    app()
