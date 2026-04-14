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
        os.close(fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        os.unlink(tmp)
        raise
    try:
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def safe_parse_py(path: Path) -> tuple[ast.Module, str] | None:
    try:
        source = path.read_text(encoding="utf-8")
        return ast.parse(source), source
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
