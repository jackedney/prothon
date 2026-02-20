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

    def diff_names(self, base_commit: str) -> set[str]: ...

    def diff_numstat(self, base_commit: str) -> DiffStat: ...


def run_git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return stdout.

    Args:
        *args: Git subcommand and arguments (e.g. "diff", "--numstat").
        cwd: Working directory for the git process.

    Returns:
        The command's stdout as a string.

    Raises:
        GitError: If the git command exits with a non-zero return code.
    """
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

    def diff_names(self, base_commit: str) -> set[str]:
        """Return set of file paths changed since *base_commit*."""
        output = run_git("diff", base_commit, "--name-only")
        return {line for line in output.strip().splitlines() if line.strip()}

    def diff_numstat(self, base_commit: str) -> DiffStat:
        """Return ``{filepath: (lines_added, lines_removed)}`` since *base_commit*.

        Binary files (reported as ``-`` by git) are skipped.
        """
        stats: DiffStat = {}
        output = run_git("diff", base_commit, "--numstat")
        for line in output.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                added_str, removed_str, filepath = parts
                if added_str == "-" or removed_str == "-":
                    continue  # binary file
                stats[filepath] = (int(added_str), int(removed_str))
        return stats


def rev_parse_head(cwd: Path | None = None) -> str:
    """Return the full SHA of HEAD.

    Args:
        cwd: Working directory for the git process.

    Returns:
        The 40-character hexadecimal SHA of the current HEAD commit.

    Raises:
        GitError: If the git command fails (e.g. not inside a git repo).
    """
    return run_git("rev-parse", "HEAD", cwd=cwd).strip()
