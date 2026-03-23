"""Implementation logic for Prothon CLI commands."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from prothon import promise, promise_verify, versioning
from prothon.assistant import get_backend, launch
from prothon.config import (
    file_hash,
    find_init_path,
    nested_get,
    read_toml,
    resolve_agent,
    resolve_model,
)
from prothon.exceptions import GitError, ProthonError
from prothon.git import commit_file, is_dirty
from prothon.models import PROMISE_PATH
from prothon.project import find_project_root
from prothon.static_checks import run_static_checks
from prothon.ui import (
    console,
    render_check_report,
    render_compliance_report,
    render_plan,
    render_status,
)


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
    Skill.SPEC_WRITER: [Path("docs/SPEC.md")],
    Skill.DESIGN_WRITER: [Path("docs/DESIGN.md")],
    Skill.PATTERNS_WRITER: [Path("docs/PATTERNS.md")],
    Skill.REFACTOR: [Path("docs/DESIGN.md"), Path("docs/PATTERNS.md")],
    Skill.DOC_HARMONIZER: [Path("docs/DESIGN.md"), Path("docs/PATTERNS.md")],
}


def require_project_root() -> Path:
    """Find the project root or raise ProthonError."""
    return find_project_root()


def require_doc(root: Path, doc_name: str) -> None:
    """Raise ProthonError if a prerequisite doc file is missing."""
    doc_path = root / "docs" / doc_name
    if not doc_path.is_file():
        raise ProthonError(f"docs/{doc_name} must exist before this command can run")


def require_promise_file(root: Path) -> Path:
    """Resolve promise path against project root, or raise ProthonError."""
    promise_path = root / PROMISE_PATH
    if not promise_path.exists():
        raise ProthonError(f"No promise file found at {promise_path}")
    return promise_path


def enforce_commit(skill_name: str, root: Path) -> None:
    """If a doc-writing skill modified a file but didn't commit, do it now."""
    try:
        s = Skill(skill_name)
    except ValueError:
        return

    doc_paths = SKILL_DOC_MAP.get(s, [])
    if not doc_paths:
        return

    for doc_path in doc_paths:
        full_path = root / doc_path
        if not full_path.exists():
            continue

        if is_dirty(doc_path, cwd=root):
            console.print(f"  Enforcing commit for {doc_path}...")
            msg = f"docs: update {doc_path.name} via {skill_name}"
            commit_file(doc_path, msg, cwd=root)


def trigger_follow_ups(
    skill_name: str,
    cwd: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> None:
    """Launch follow-up sessions based on the completed skill and file changes."""
    if skill_name in (Skill.SPEC_WRITER, Skill.DESIGN_WRITER, Skill.PATTERNS_WRITER):
        console.print("\n  Triggering doc-harmonizer...")
        launch_skill(
            Skill.DOC_HARMONIZER,
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )

    if skill_name == Skill.DESIGN_WRITER:
        console.print("\n  Triggering tech-researcher...")
        launch_skill(
            Skill.TECH_RESEARCHER,
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )

    if skill_name == Skill.EXECUTE:
        console.print("\n  Triggering compliance-checker...")
        launch_skill(
            Skill.COMPLIANCE,
            cwd,
            agent,
            model,
            provider,
            run_follow_ups=False,
        )


def launch_skill(
    skill_name: str,
    cwd: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    run_follow_ups: bool = True,
) -> int:
    """Resolve backend, launch skill, handle errors, and enforce lifecycle.

    Returns:
        Exit code from the assistant process.
    """
    spec_path = cwd / "docs" / "SPEC.md"
    guard_spec = skill_name != Skill.SPEC_WRITER
    spec_hash = file_hash(spec_path) if guard_spec else None

    name = resolve_agent(agent)
    backend = get_backend(name)
    resolved_model = resolve_model(model, provider) if name == "opencode" else None
    rc = launch(backend, skill_name, cwd, model=resolved_model)

    if guard_spec and file_hash(spec_path) != spec_hash:
        console.print(
            "Warning: docs/SPEC.md was modified outside of 'prothon spec'. "
            "Only the spec-writer should modify SPEC.md.",
            style="yellow",
        )

    if rc == 0:
        enforce_commit(skill_name, cwd)
        if run_follow_ups:
            trigger_follow_ups(skill_name, cwd, agent, model, provider)

    return rc


def compliance_command(
    root: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> None:
    """Implementation for the compliance command."""
    # Step 1: Deterministic Static Analysis
    report = run_static_checks(root)

    # Step 2: Semantic Analysis (LLM)
    prothon_dir = root / ".prothon"
    prothon_dir.mkdir(parents=True, exist_ok=True)
    results_path = prothon_dir / "compliance_semantic.json"
    if results_path.exists():
        results_path.unlink()

    console.print("Launching semantic compliance checks (LLM)...")
    try:
        launch_skill(Skill.COMPLIANCE, root, agent, model, provider)
    except ProthonError as exc:
        console.print(
            f"Warning: Semantic checks failed to launch: {exc}", style="yellow"
        )

    # Step 3: Merge and display unified report
    if results_path.exists():
        try:
            with open(results_path, encoding="utf-8") as f:
                findings = json.load(f)
            report.add_from_dicts(findings)
        except (OSError, json.JSONDecodeError) as exc:
            console.print(
                f"Warning: Failed to load semantic compliance results: {exc}",
                style="yellow",
            )
    else:
        console.print(
            "Warning: No semantic results found. The assistant session might have "
            "exited without producing a report or was cancelled.",
            style="yellow",
        )

    console.print("\n", render_compliance_report(report))
    console.print("\n" + report.format_summary())


def ci_bump_command(
    root: Path,
    before_sha: str,
    after_sha: str = "HEAD",
    dry_run: bool = False,
    no_tag: bool = False,
) -> None:
    """Implementation for the ci bump command."""
    pyproject_path = root / "pyproject.toml"

    doc = read_toml(pyproject_path)
    if not doc:
        raise ProthonError("Could not read pyproject.toml")

    auto_version = nested_get(doc, "tool", "prothon", "ci", "auto_version")
    if auto_version is not None and str(auto_version).lower() in ("false", "0", "no"):
        console.print("Automatic versioning is disabled in pyproject.toml")
        return

    bump_type = versioning.detect_bump_type(before_sha, after_sha, cwd=root)
    if not bump_type:
        console.print("No version bump needed (no relevant files changed).")
        return

    branch_version = nested_get(doc, "project", "version")
    if not branch_version:
        raise ProthonError("[project] version not found in pyproject.toml")

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
        console.print(
            f"Warning: Could not read pyproject.toml from {before_sha}: {exc}",
            style="yellow",
        )
        base_version = None

    if not base_version:
        console.print(f"Falling back to branch version {branch_version} as base")
        base_version = branch_version

    bump_fn = getattr(versioning, f"bump_{bump_type}")
    expected_version = bump_fn(base_version)

    if branch_version == expected_version:
        console.print(f"Version already at {expected_version}, skipping.")
        return

    console.print(f"Detected {bump_type} bump: {base_version} -> {expected_version}")

    if dry_run:
        console.print("Dry run: Skipping file updates and tagging.")
        return

    versioning.update_pyproject_version(pyproject_path, expected_version)

    project_name = nested_get(doc, "project", "name")
    if not project_name:
        raise ProthonError("[project] name not found in pyproject.toml")

    module_name = project_name.replace("-", "_")
    init_path = find_init_path(root, project_name, module_name)

    if init_path:
        versioning.update_init_version(init_path, expected_version)
        console.print(f"Updated {init_path.relative_to(root)}")
    else:
        console.print(
            f"Warning: Could not find __init__.py in src/{module_name} "
            f"or src/{project_name}",
            style="yellow",
        )

    if not no_tag:
        try:
            versioning.create_tag(expected_version, cwd=root)
            console.print(f"Created tag v{expected_version}")
        except ProthonError as exc:
            console.print(f"Warning: Tag creation failed: {exc}", style="yellow")


def ci_detect_command(root: Path, before_sha: str, after_sha: str = "HEAD") -> None:
    """Implementation for the ci detect command."""
    bump_type = versioning.detect_bump_type(before_sha, after_sha, cwd=root)
    if bump_type:
        console.print(bump_type)
    else:
        console.print("none")


def promise_plan_command(root: Path) -> None:
    """Pretty-print the change promise plan."""
    promise_path = require_promise_file(root)
    p = promise.load_promise(promise_path)
    console.print(render_plan(p))


def promise_status_command(root: Path) -> None:
    """Show completion status of all tasks."""
    promise_path = require_promise_file(root)
    p = promise.load_promise(promise_path)
    console.print(render_status(p))


def promise_check_command(root: Path, task_index: int) -> None:
    """Verify a task's promises against git reality."""
    promise_path = require_promise_file(root)
    report = promise_verify.check_task(task_index, path=promise_path)
    console.print(render_check_report(report))
    if not report.passed:
        raise ProthonError("Task check failed")


def promise_complete_command(root: Path, task_index: int) -> None:
    """Mark a task as completed."""
    promise_path = require_promise_file(root)
    promise.complete_task(task_index, path=promise_path)
    console.print(f"Task {task_index} marked as completed.")


def promise_record_attempt_command(root: Path, task_index: int) -> None:
    """Increment the attempt counter for a task."""
    promise_path = require_promise_file(root)
    promise.record_attempt(task_index, path=promise_path)
    console.print(f"Attempt recorded for task {task_index}.")


def promise_cleanup_command(root: Path) -> None:
    """Remove the promise file after all tasks are complete."""
    promise_path = require_promise_file(root)
    promise.cleanup(promise_path)
    console.print("Promise file removed.")


def spec_command(
    root: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> int:
    """Write or revise SPEC.md."""
    return launch_skill(Skill.SPEC_WRITER, root, agent, model, provider)


def design_command(
    root: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> int:
    """Write or revise DESIGN.md."""
    require_doc(root, "SPEC.md")
    return launch_skill(Skill.DESIGN_WRITER, root, agent, model, provider)


def patterns_command(
    root: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> int:
    """Write or revise PATTERNS.md."""
    require_doc(root, "DESIGN.md")
    return launch_skill(Skill.PATTERNS_WRITER, root, agent, model, provider)


def execute_command(
    root: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> int:
    """Align source code to documentation."""
    return launch_skill(Skill.EXECUTE, root, agent, model, provider)


def refactor_command(
    root: Path,
    agent: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> int:
    """Perform documentation-driven full-stack refactoring."""
    require_doc(root, "SPEC.md")
    require_doc(root, "DESIGN.md")
    require_doc(root, "PATTERNS.md")
    return launch_skill(Skill.REFACTOR, root, agent, model, provider)
