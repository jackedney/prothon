"""Tests for prothon.checks.research — tech researcher and versioning checks.

Covers edge cases for check_tech_researcher and check_semantic_versioning:
empty skills directories, Key Decisions detection, mixed violations,
and partial CI template scenarios.
"""

from __future__ import annotations

from pathlib import Path

from prothon.checks.research import check_semantic_versioning, check_tech_researcher
from prothon.compliance import CheckStatus


# ---------------------------------------------------------------------------
# check_tech_researcher — empty skills dir edge cases
# ---------------------------------------------------------------------------


def test_empty_skills_dir_with_tech_choices(tmp_path: Path) -> None:
    """R45 FAIL when .agents/skills/ exists but is empty and DESIGN.md has tech choices."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "DESIGN.md").write_text("# Design\n## Technology Choices\nPython\n")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert "empty" in r45.rationale.lower()


def test_empty_skills_dir_without_tech_choices(tmp_path: Path) -> None:
    """R45 PASS when .agents/skills/ exists but is empty and no tech choices."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.PASS


def test_key_decisions_triggers_tech_detection(tmp_path: Path) -> None:
    """R45 FAIL when DESIGN.md has 'Key Decisions' instead of 'Technology Choices'."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "DESIGN.md").write_text("# Design\n## Key Decisions\nUse FastAPI.\n")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL


def test_mixed_violations_in_skill_folders(tmp_path: Path) -> None:
    """R45 FAIL with both non-kebab-case and missing SKILL.md violations."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)

    non_kebab = skills_dir / "NotKebab"
    non_kebab.mkdir()
    (non_kebab / "SKILL.md").write_text("# Bad Name")

    missing_md = skills_dir / "valid-name"
    missing_md.mkdir()

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert "not kebab-case" in r45.rationale
    assert "missing SKILL.md" in r45.rationale


def test_skills_dir_with_files_not_dirs(tmp_path: Path) -> None:
    """R45 PASS when .agents/skills/ contains only regular files (no subdirectories)."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "README.md").write_text("not a directory")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# check_semantic_versioning — partial template scenarios
# ---------------------------------------------------------------------------


def test_semantic_versioning_only_tag_template(tmp_path: Path) -> None:
    """R53 PASS when tag template exists but bump templates are missing."""
    gh = tmp_path / "template" / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-tag.yml.jinja").write_text("")

    results = check_semantic_versioning(tmp_path)
    r53 = next(r for r in results if r.requirement.requirement_id == "R53")
    r55 = next(r for r in results if r.requirement.requirement_id == "R55")
    assert r53.status == CheckStatus.PASS
    assert r55.status == CheckStatus.FAIL


def test_semantic_versioning_only_gitlab_bump(tmp_path: Path) -> None:
    """R55 FAIL when only GitLab template exists (missing GitHub bump)."""
    gh = tmp_path / "template" / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-tag.yml.jinja").write_text("")
    (tmp_path / "template" / ".gitlab-ci.yml.jinja").write_text("")

    results = check_semantic_versioning(tmp_path)
    r55 = next(r for r in results if r.requirement.requirement_id == "R55")
    assert r55.status == CheckStatus.FAIL
    assert "version-bump" in r55.rationale
