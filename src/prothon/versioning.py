"""Semantic version detection, bumping, and git tagging."""

from __future__ import annotations

import re
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from prothon.config import find_init_path, nested_get, read_toml
from prothon.exceptions import GitError, ProthonError, VersionError
from prothon.git import run_git
from prothon.ui import console


def parse_version(v: str) -> tuple[int, int, int]:
    """Parse ``"v1.2.3"`` or ``"1.2.3"`` into ``(major, minor, patch)``."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", v)
    if not match:
        raise VersionError(f"invalid version format: {v!r}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def bump_major(v: str) -> str:
    major, _, _ = parse_version(v)
    return f"{major + 1}.0.0"


def bump_minor(v: str) -> str:
    major, minor, _ = parse_version(v)
    return f"{major}.{minor + 1}.0"


def bump_patch(v: str) -> str:
    major, minor, patch = parse_version(v)
    return f"{major}.{minor}.{patch + 1}"


def update_pyproject_version(path: Path, new_version: str) -> None:
    """Update the version field in pyproject.toml, preserving formatting."""
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
        project = doc.get("project")
        if not isinstance(project, dict):
            raise VersionError("pyproject.toml missing [project] table")
        project["version"] = new_version
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    except TOMLKitError as exc:
        raise VersionError(f"failed to update pyproject.toml: {exc}") from exc


def update_init_version(path: Path, new_version: str) -> None:
    content = path.read_text(encoding="utf-8")
    pattern = r'__version__\s*=\s*["\'][^"\']+["\']'
    if not re.search(pattern, content):
        raise VersionError(f"no __version__ assignment found in {path}")
    updated = re.sub(pattern, f'__version__ = "{new_version}"', content)
    path.write_text(updated, encoding="utf-8")


def create_tag(version: str, cwd: Path | None = None) -> None:
    run_git("tag", "-a", f"v{version}", "-m", f"release {version}", cwd=cwd)


def detect_bump_type(
    before_sha: str, after_sha: str, cwd: Path | None = None
) -> str | None:
    """Priority: SPEC.md (major) > DESIGN.md (minor) > PATTERNS.md or src/ (patch)."""
    output = run_git("diff", "--name-only", before_sha, after_sha, cwd=cwd)
    files = {line for line in output.strip().splitlines() if line.strip()}

    if "docs/SPEC.md" in files:
        return "major"
    if "docs/DESIGN.md" in files:
        return "minor"
    if "docs/PATTERNS.md" in files or any(f.startswith("src/") for f in files):
        return "patch"
    return None


def _read_init_version(init_path: Path) -> str | None:
    content = init_path.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else None


def _resolve_base_version(before_sha: str, root: Path) -> str | None:
    try:
        base_toml_content = run_git("show", f"{before_sha}:pyproject.toml", cwd=root)
        base_doc = tomlkit.parse(base_toml_content)
        return nested_get(base_doc, "project", "version")
    except (
        GitError,
        FileNotFoundError,
        TOMLKitError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        console.print(
            f"Warning: Could not read pyproject.toml from {before_sha}: {exc}",
            style="yellow",
        )
        return None


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

    bump_type = detect_bump_type(before_sha, after_sha, cwd=root)
    if not bump_type:
        console.print("No version bump needed (no relevant files changed).")
        return

    branch_version = nested_get(doc, "project", "version")
    if not branch_version:
        raise ProthonError("[project] version not found in pyproject.toml")

    base_version = _resolve_base_version(before_sha, root)
    if not base_version:
        console.print(f"Falling back to branch version {branch_version} as base")
        base_version = branch_version

    bump_fn = globals()[f"bump_{bump_type}"]
    expected_version = bump_fn(base_version)

    project_name = nested_get(doc, "project", "name")
    if not project_name:
        raise ProthonError("[project] name not found in pyproject.toml")

    module_name = project_name.replace("-", "_")
    init_path = find_init_path(root, project_name, module_name)

    init_version = _read_init_version(init_path) if init_path else None

    if branch_version == expected_version and init_version == expected_version:
        console.print(f"Version already at {expected_version}, skipping.")
        return

    console.print(f"Detected {bump_type} bump: {base_version} -> {expected_version}")

    if dry_run:
        console.print("Dry run: Skipping file updates and tagging.")
        return

    if init_path:
        update_init_version(init_path, expected_version)
        console.print(f"Updated {init_path.relative_to(root)}")
    else:
        console.print(
            f"Warning: Could not find __init__.py in src/{module_name} "
            f"or src/{project_name}",
            style="yellow",
        )

    update_pyproject_version(pyproject_path, expected_version)

    if not no_tag:
        try:
            create_tag(expected_version, cwd=root)
            console.print(f"Created tag v{expected_version}")
        except ProthonError as exc:
            console.print(f"Warning: Tag creation failed: {exc}", style="yellow")


def ci_detect_command(root: Path, before_sha: str, after_sha: str = "HEAD") -> None:
    """Implementation for the ci detect command."""
    bump_type = detect_bump_type(before_sha, after_sha, cwd=root)
    if bump_type:
        console.print(bump_type)
    else:
        console.print("none")
