"""Semantic version detection, bumping, and git tagging."""

from __future__ import annotations

import re
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from prothon.exceptions import VersionError
from prothon.git import run_git


def parse_version(v: str) -> tuple[int, int, int]:
    """Parse a semantic version string into (major, minor, patch) tuple.

    Args:
        v: Version string, optionally prefixed with 'v' (e.g. "1.2.3" or "v1.2.3").

    Returns:
        A tuple of (major, minor, patch) integers.

    Raises:
        VersionError: If the version string is not in valid semver format.
    """
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", v)
    if not match:
        raise VersionError(f"invalid version format: {v!r}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def bump_major(v: str) -> str:
    """Bump the major version, resetting minor and patch to 0.

    Args:
        v: Version string to bump.

    Returns:
        New version string with major incremented, minor and patch reset.

    Raises:
        VersionError: If the version string is malformed.
    """
    major, _, _ = parse_version(v)
    return f"{major + 1}.0.0"


def bump_minor(v: str) -> str:
    """Bump the minor version, resetting patch to 0.

    Args:
        v: Version string to bump.

    Returns:
        New version string with minor incremented, patch reset.

    Raises:
        VersionError: If the version string is malformed.
    """
    major, minor, _ = parse_version(v)
    return f"{major}.{minor + 1}.0"


def bump_patch(v: str) -> str:
    """Bump the patch version.

    Args:
        v: Version string to bump.

    Returns:
        New version string with patch incremented.

    Raises:
        VersionError: If the version string is malformed.
    """
    major, minor, patch = parse_version(v)
    return f"{major}.{minor}.{patch + 1}"


def update_pyproject_version(path: Path, new_version: str) -> None:
    """Update the version field in pyproject.toml, preserving formatting.

    Args:
        path: Path to the pyproject.toml file.
        new_version: New version string to write.

    Raises:
        VersionError: If the file cannot be parsed or lacks [project] table.
    """
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
    """Update the __version__ string in an __init__.py file.

    Args:
        path: Path to the __init__.py file.
        new_version: New version string to write.

    Raises:
        VersionError: If the file has no __version__ assignment.
    """
    content = path.read_text(encoding="utf-8")
    pattern = r'__version__\s*=\s*["\'][^"\']+["\']'
    if not re.search(pattern, content):
        raise VersionError(f"no __version__ assignment found in {path}")
    updated = re.sub(pattern, f'__version__ = "{new_version}"', content)
    path.write_text(updated, encoding="utf-8")


def create_tag(version: str, cwd: Path | None = None) -> None:
    """Create an annotated git tag for the given version.

    Args:
        version: Version string (without 'v' prefix).
        cwd: Working directory for the git process.

    Raises:
        GitError: If the git command fails.
    """
    run_git("tag", "-a", f"v{version}", "-m", f"release {version}", cwd=cwd)


def detect_bump_type(
    before_sha: str, after_sha: str, cwd: Path | None = None
) -> str | None:
    """Detect which version bump type applies based on changed files.

    Priority: SPEC.md (major) > DESIGN.md (minor) > PATTERNS.md or src/ (patch).

    Args:
        before_sha: Git SHA to diff from.
        after_sha: Git SHA to diff to.
        cwd: Working directory for the git process.

    Returns:
        "major", "minor", "patch", or None if no relevant files changed.

    Raises:
        GitError: If the git command fails.
    """
    output = run_git("diff", "--name-only", before_sha, after_sha, cwd=cwd)
    files = {line for line in output.strip().splitlines() if line.strip()}

    if "docs/SPEC.md" in files:
        return "major"
    if "docs/DESIGN.md" in files:
        return "minor"
    if "docs/PATTERNS.md" in files or any(f.startswith("src/") for f in files):
        return "patch"
    return None
