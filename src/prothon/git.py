"""Thin typed wrapper around git CLI via subprocess."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Protocol

from prothon.exceptions import GitError

DiffStat = dict[str, tuple[int, int]]


class GitDiffProvider(Protocol):
    """Protocol for git diff data sources -- real or fake for testing."""

    def diff_names(self, base_commit: str, *paths: str) -> set[str]: ...

    def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat: ...


def run_git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode != 0:
        full_cmd = " ".join(["git", *args])
        raise GitError(
            f"{full_cmd} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


class SubprocessGitDiff:
    """Real git diff provider that shells out to git CLI."""

    def diff_names(self, base_commit: str, *paths: str) -> set[str]:
        """Return set of file paths changed since *base_commit*."""
        cmd = ["diff", base_commit, "--name-only"]
        if paths:
            cmd.extend(["--", *paths])
        output = run_git(*cmd)
        return {line for line in output.strip().splitlines() if line.strip()}

    def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat:
        """Return ``{filepath: (lines_added, lines_removed)}`` since *base_commit*.

        Binary files (reported as ``-`` by git) are skipped.
        """
        stats: DiffStat = {}
        cmd = ["diff", base_commit, "--numstat"]
        if paths:
            cmd.extend(["--", *paths])
        output = run_git(*cmd)
        for line in output.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                added_str, removed_str, filepath = parts
                if added_str == "-" or removed_str == "-":
                    continue  # binary file
                stats[filepath] = (int(added_str), int(removed_str))
        return stats


def rev_parse_head(cwd: Path | None = None) -> str:
    return run_git("rev-parse", "HEAD", cwd=cwd).strip()


def is_dirty(path: Path, cwd: Path | None = None) -> bool:
    output = run_git("status", "--porcelain", "--", str(path), cwd=cwd).strip()
    return bool(output)


def commit_file(path: Path, message: str, cwd: Path | None = None) -> None:
    run_git("add", "--", str(path), cwd=cwd)
    run_git("commit", "-m", message, "--", str(path), cwd=cwd)


def run_pre_commit(paths: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run pre-commit hooks on a specific set of files.

    Returns:
        A tuple of (returncode, combined_output).
    """
    if not paths:
        return 0, ""

    # Use 'uv run pre-commit' if in a uv-managed project, otherwise 'pre-commit'
    cmd = ["pre-commit", "run", "--files", *paths]
    if (cwd or Path.cwd() / "uv.lock").exists():
        cmd = ["uv", "run", "pre-commit", "run", "--files", *paths]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=os.environ,
    )
    return result.returncode, result.stdout + result.stderr
