from __future__ import annotations

import ast
import os
import shutil
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise
    os.close(fd)
    try:
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def safe_parse_py(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


def xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw and Path(raw).is_absolute():
        return Path(raw)
    return Path.home() / ".config"


def create_agent_symlinks(root: Path, agents_path: Path) -> list[Path]:
    created = []
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = root / name
        if not link.exists():
            try:
                os.symlink("AGENTS.md", link)
            except OSError:
                shutil.copyfile(agents_path, link)
            created.append(link)
    return created
