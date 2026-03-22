"""Tests for skill discovery and synchronization."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prothon.skills import bundled_skills_dir, sync_skills


def test_bundled_skills_dir_exists():
    """bundled_skills_dir() must return an existing directory."""
    path = bundled_skills_dir()
    assert isinstance(path, Path)
    assert path.is_dir()
    # At least one skill should be bundled
    assert any(path.iterdir())


def test_sync_skills_creates_symlinks(tmp_path):
    """sync_skills() must create symlinks in the target directory."""
    target = tmp_path / "target_skills"
    sync_skills(target=target)

    assert target.is_dir()
    bundled = bundled_skills_dir()

    # Verify each bundled skill directory is symlinked
    for skill_dir in bundled.iterdir():
        if skill_dir.is_dir():
            dest = target / skill_dir.name
            assert dest.is_symlink()
            assert dest.resolve() == skill_dir.resolve()


def test_sync_skills_cleans_up_existing_symlinks(tmp_path):
    """sync_skills() must replace existing symlinks."""
    target = tmp_path / "target_skills"
    target.mkdir()

    bundled = bundled_skills_dir()
    # Pick the first skill and create a dummy symlink
    first_skill = next(s for s in bundled.iterdir() if s.is_dir())
    dummy_link = target / first_skill.name
    dummy_link.symlink_to(tmp_path)  # Points to wrong place

    sync_skills(target=target)

    assert dummy_link.is_symlink()
    assert dummy_link.resolve() == first_skill.resolve()


def test_sync_skills_cleans_up_existing_directories(tmp_path):
    """sync_skills() must replace existing directories with symlinks."""
    target = tmp_path / "target_skills"
    target.mkdir()

    bundled = bundled_skills_dir()
    first_skill = next(s for s in bundled.iterdir() if s.is_dir())
    dummy_dir = target / first_skill.name
    dummy_dir.mkdir()
    (dummy_dir / "marker.txt").write_text("should be gone")

    sync_skills(target=target)

    dummy_link = target / first_skill.name
    assert dummy_link.is_symlink()
    assert dummy_link.resolve() == first_skill.resolve()
    assert not (dummy_dir / "marker.txt").exists()


@patch("pathlib.Path.home")
def test_sync_skills_default_target(mock_home, tmp_path):
    """sync_skills() must use ~/.claude/skills/ by default."""
    # Mock home to a temp directory to avoid touching real filesystem
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    mock_home.return_value = fake_home

    # We don't want to actually create ~/.claude/skills in real home
    # But since we mocked Path.home, it will use fake_home
    sync_skills()

    expected_target = fake_home / ".claude" / "skills"
    assert expected_target.is_dir()
    # Check if at least one symlink exists there
    assert any(expected_target.iterdir())
