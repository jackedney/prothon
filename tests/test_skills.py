"""Tests for skill discovery and symlink management."""

from __future__ import annotations

from pathlib import Path

from prothon.skills import bundled_skills_dir, sync_skills


def test_bundled_skills_dir_returns_correct_path() -> None:
    """bundled_skills_dir() points to the skills/ directory inside the package."""
    result = bundled_skills_dir()
    assert (
        result == Path(__file__).resolve().parent.parent / "src" / "prothon" / "skills"
    )
    assert result.is_dir()


def test_sync_skills_creates_symlinks(tmp_path: Path) -> None:
    """sync_skills creates a symlink for each bundled skill directory."""
    target = tmp_path / "skills"
    sync_skills(target=target)

    bundled = bundled_skills_dir()
    bundled_dirs = [d for d in bundled.iterdir() if d.is_dir()]

    assert target.is_dir()
    for skill_dir in bundled_dirs:
        link = target / skill_dir.name
        assert link.is_symlink()
        assert link.resolve() == skill_dir.resolve()


def test_sync_skills_handles_broken_symlinks(tmp_path: Path) -> None:
    """sync_skills removes broken symlinks and recreates them correctly."""
    target = tmp_path / "skills"
    target.mkdir(parents=True)

    # Create a broken symlink pointing to a nonexistent path
    broken = target / "prothon-spec-writer"
    broken.symlink_to(tmp_path / "nonexistent")
    assert broken.is_symlink()
    assert not broken.exists()  # broken: target doesn't exist

    sync_skills(target=target)

    # The broken symlink should now point to the real bundled skill
    assert broken.is_symlink()
    assert broken.exists()  # no longer broken


def test_sync_skills_is_idempotent(tmp_path: Path) -> None:
    """Running sync_skills twice produces the same result."""
    target = tmp_path / "skills"

    sync_skills(target=target)
    first_links = {p.name: p.resolve() for p in target.iterdir() if p.is_symlink()}

    sync_skills(target=target)
    second_links = {p.name: p.resolve() for p in target.iterdir() if p.is_symlink()}

    assert first_links == second_links


def test_sync_skills_replaces_non_symlink_dir(tmp_path: Path) -> None:
    """sync_skills replaces an existing non-symlink directory with a symlink."""
    target = tmp_path / "skills"
    target.mkdir(parents=True)

    # Create a real directory where a symlink should go
    blocker = target / "prothon-spec-writer"
    blocker.mkdir()
    (blocker / "stale.txt").write_text("stale")

    sync_skills(target=target)

    assert blocker.is_symlink()
    assert blocker.exists()
