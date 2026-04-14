"""Shared filesystem utilities."""

from __future__ import annotations

import ast
import hashlib
import os
import tempfile
from pathlib import Path


def file_hash(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if unreadable."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def atomic_write(target: Path, data: bytes) -> None:
    """Write *data* to *target* atomically via a temp file rename."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name)
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def safe_parse_py(path: Path) -> tuple[ast.Module, str] | None:
    """Parse a Python file, returning (tree, source) or None on error."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        return tree, source
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def xdg_config_home() -> Path:
    """Return the XDG_CONFIG_HOME directory, defaulting to ~/.config."""
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw and Path(raw).is_absolute():
        return Path(raw)
    return Path.home() / ".config"


def create_agent_symlinks(root: Path, agents_path: Path) -> list[Path]:
    """Create CLAUDE.md, GEMINI.md, AGENT.md symlinks pointing to agents_path.

    Returns a list of newly created symlink paths (empty if all already exist).
    """
    created: list[Path] = []
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = root / name
        if link.exists() or link.is_symlink():
            continue
        link.symlink_to(agents_path.name)
        created.append(link)
    return created
