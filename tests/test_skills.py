"""Tests for skill discovery and symlink management."""

from __future__ import annotations

from pathlib import Path

import pytest
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


def test_sync_skills_skips_non_directory_entries(tmp_path: Path) -> None:
    """sync_skills only processes directories in the bundled skills dir."""
    target = tmp_path / "skills"
    sync_skills(target=target)

    # Verify no non-directory bundled entries became symlinks
    bundled = bundled_skills_dir()
    non_dirs = [e for e in bundled.iterdir() if not e.is_dir()]
    for entry in non_dirs:
        assert not (target / entry.name).exists()


def test_sync_skills_replaces_regular_file(tmp_path: Path) -> None:
    """sync_skills replaces a regular file with a symlink."""
    target = tmp_path / "skills"
    target.mkdir(parents=True)

    bundled = bundled_skills_dir()
    bundled_dirs = [d for d in bundled.iterdir() if d.is_dir()]
    if not bundled_dirs:
        pytest.skip("No bundled skill dirs")

    # Create a regular file where a symlink should go
    blocker = target / bundled_dirs[0].name
    blocker.write_text("blocking file")

    sync_skills(target=target)

    assert blocker.is_symlink()
    assert blocker.resolve() == bundled_dirs[0].resolve()


def test_sync_skills_symlink_targets_are_resolved(tmp_path: Path) -> None:
    """Symlinks point to resolved (absolute) paths."""
    target = tmp_path / "skills"
    sync_skills(target=target)

    for link in target.iterdir():
        if link.is_symlink():
            link_target = link.readlink()
            assert link_target.is_absolute()


def test_sync_skills_creates_target_dir(tmp_path: Path) -> None:
    """sync_skills creates the target directory if it doesn't exist."""
    target = tmp_path / "deep" / "nested" / "skills"
    assert not target.exists()
    sync_skills(target=target)
    assert target.is_dir()


def test_sync_skills_default_target_path() -> None:
    """sync_skills without target arg uses ~/.claude/skills."""
    from unittest.mock import patch as mock_patch

    with mock_patch("prothon.skills.bundled_skills_dir") as mock_bundled:
        # Return a fake dir that doesn't exist so it returns early
        mock_bundled.return_value = Path("/nonexistent/skills")
        # Should not crash even with default target
        sync_skills()


def test_sync_skills_continue_processes_all_dirs(tmp_path: Path) -> None:
    """continue (not break) on non-dir entries -- all skill dirs get symlinked."""
    target = tmp_path / "skills"
    sync_skills(target=target)

    bundled = bundled_skills_dir()
    bundled_dirs = sorted(d.name for d in bundled.iterdir() if d.is_dir())

    linked = sorted(p.name for p in target.iterdir() if p.is_symlink())
    assert linked == bundled_dirs


def test_sync_skills_default_path_uses_home_claude_skills(tmp_path: Path) -> None:
    """sync_skills() without target= uses ~/.claude/skills/ (kills default path mutations)."""
    from unittest.mock import patch as mock_patch

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()

    with mock_patch("prothon.skills.Path.home", return_value=fake_home):
        sync_skills()

    expected_target = fake_home / ".claude" / "skills"
    assert expected_target.is_dir()

    bundled = bundled_skills_dir()
    bundled_dirs = [d for d in bundled.iterdir() if d.is_dir()]
    for skill_dir in bundled_dirs:
        link = expected_target / skill_dir.name
        assert link.is_symlink()
        assert link.resolve() == skill_dir.resolve()
