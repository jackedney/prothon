"""Tests for enforce_commit logic in commands.py."""

from __future__ import annotations

from pathlib import Path
from tests.fakes import Recorder
from prothon.commands import enforce_commit


def test_enforce_commit_multiple_docs_for_refactor(tmp_path, monkeypatch):
    """Refactor skill can commit both DESIGN.md and PATTERNS.md if dirty."""
    (tmp_path / "docs").mkdir()
    design = tmp_path / "docs" / "DESIGN.md"
    patterns = tmp_path / "docs" / "PATTERNS.md"
    design.write_text("# Design\n")
    patterns.write_text("# Patterns\n")

    fake_commit = Recorder()
    # Mock is_dirty to return True for both
    monkeypatch.setattr("prothon.commands.is_dirty", lambda path, cwd: True)
    monkeypatch.setattr("prothon.commands.commit_file", fake_commit)

    enforce_commit("prothon-refactor", tmp_path)

    assert fake_commit.call_count == 2
    # Check first commit (DESIGN.md)
    assert fake_commit.calls[0][0][0] == Path("docs/DESIGN.md")
    assert "DESIGN.md" in fake_commit.calls[0][0][1]
    assert "prothon-refactor" in fake_commit.calls[0][0][1]

    # Check second commit (PATTERNS.md)
    assert fake_commit.calls[1][0][0] == Path("docs/PATTERNS.md")
    assert "PATTERNS.md" in fake_commit.calls[1][0][1]
    assert "prothon-refactor" in fake_commit.calls[1][0][1]


def test_enforce_commit_multiple_docs_for_harmonizer(tmp_path, monkeypatch):
    """Doc-harmonizer skill can commit both DESIGN.md and PATTERNS.md if dirty."""
    (tmp_path / "docs").mkdir()
    design = tmp_path / "docs" / "DESIGN.md"
    patterns = tmp_path / "docs" / "PATTERNS.md"
    design.write_text("# Design\n")
    patterns.write_text("# Patterns\n")

    fake_commit = Recorder()
    # Mock is_dirty to return True for both
    monkeypatch.setattr("prothon.commands.is_dirty", lambda path, cwd: True)
    monkeypatch.setattr("prothon.commands.commit_file", fake_commit)

    enforce_commit("prothon-doc-harmonizer", tmp_path)

    assert fake_commit.call_count == 2
    assert fake_commit.calls[0][0][0] == Path("docs/DESIGN.md")
    assert fake_commit.calls[1][0][0] == Path("docs/PATTERNS.md")


def test_enforce_commit_skips_missing_files(tmp_path, monkeypatch):
    """If one of the mapped docs doesn't exist, it is skipped without error."""
    (tmp_path / "docs").mkdir()
    design = tmp_path / "docs" / "DESIGN.md"
    design.write_text("# Design\n")
    # PATTERNS.md does not exist

    fake_commit = Recorder()
    monkeypatch.setattr("prothon.commands.is_dirty", lambda path, cwd: True)
    monkeypatch.setattr("prothon.commands.commit_file", fake_commit)

    enforce_commit("prothon-refactor", tmp_path)

    # Only DESIGN.md should be committed
    assert fake_commit.call_count == 1
    assert fake_commit.last_args[0] == Path("docs/DESIGN.md")


def test_enforce_commit_skips_clean_files(tmp_path, monkeypatch):
    """If a file is clean, it is not committed."""
    (tmp_path / "docs").mkdir()
    design = tmp_path / "docs" / "DESIGN.md"
    patterns = tmp_path / "docs" / "PATTERNS.md"
    design.write_text("# Design\n")
    patterns.write_text("# Patterns\n")

    fake_commit = Recorder()

    # DESIGN is dirty, PATTERNS is clean
    def mock_is_dirty(path, cwd):
        return "DESIGN.md" in str(path)

    monkeypatch.setattr("prothon.commands.is_dirty", mock_is_dirty)
    monkeypatch.setattr("prothon.commands.commit_file", fake_commit)

    enforce_commit("prothon-refactor", tmp_path)

    assert fake_commit.call_count == 1
    assert fake_commit.last_args[0] == Path("docs/DESIGN.md")
