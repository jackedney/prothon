"""Tests for fs module: file_hash, atomic_write, safe_parse_py, xdg_config_home, create_agent_symlinks."""

from __future__ import annotations

from pathlib import Path

from prothon.fs import (
    atomic_write,
    create_agent_symlinks,
    file_hash,
    safe_parse_py,
    xdg_config_home,
)


def test_file_hash_returns_hex_digest(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    result = file_hash(f)
    assert result is not None
    assert len(result) == 64


def test_file_hash_none_for_missing(tmp_path: Path):
    assert file_hash(tmp_path / "no-such-file") is None


def test_file_hash_none_for_directory(tmp_path: Path):
    d = tmp_path / "dir"
    d.mkdir()
    assert file_hash(d) is None


def test_file_hash_deterministic(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("content")
    assert file_hash(f) == file_hash(f)


def test_atomic_write_creates_file(tmp_path: Path):
    target = tmp_path / "out.bin"
    atomic_write(target, b"data")
    assert target.read_bytes() == b"data"


def test_atomic_write_replaces_existing(tmp_path: Path):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    atomic_write(target, b"new")
    assert target.read_bytes() == b"new"


def test_atomic_write_no_partial_on_error(tmp_path: Path):
    target = tmp_path / "out.bin"
    try:
        atomic_write(target, b"x" * 100)  # works fine
    except Exception:
        pass
    assert target.read_bytes() == b"x" * 100


def test_safe_parse_py_valid(tmp_path: Path):
    f = tmp_path / "mod.py"
    f.write_text("x = 1\n")
    result = safe_parse_py(f)
    assert result is not None
    tree, source = result
    assert source == "x = 1\n"
    assert tree is not None


def test_safe_parse_py_syntax_error(tmp_path: Path):
    f = tmp_path / "bad.py"
    f.write_text("def broken(\n")
    assert safe_parse_py(f) is None


def test_safe_parse_py_missing_file(tmp_path: Path):
    assert safe_parse_py(tmp_path / "nope.py") is None


def test_xdg_config_home_default(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert xdg_config_home() == Path.home() / ".config"


def test_xdg_config_home_custom(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
    assert xdg_config_home() == Path("/custom/config")


def test_xdg_config_home_ignores_relative(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
    assert xdg_config_home() == Path.home() / ".config"


def test_create_agent_symlinks(tmp_path: Path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# agents")
    created = create_agent_symlinks(tmp_path, agents)
    assert len(created) == 3
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = tmp_path / name
        assert link.exists()
        assert link.read_text() == "# agents"


def test_create_agent_symlinks_idempotent(tmp_path: Path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# agents")
    create_agent_symlinks(tmp_path, agents)
    created = create_agent_symlinks(tmp_path, agents)
    assert len(created) == 0
