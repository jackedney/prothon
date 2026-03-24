from __future__ import annotations

from pathlib import Path
from prothon.compliance import CheckStatus
from prothon.checks import check_tech_researcher


def test_check_tech_researcher_all_present_and_compliant(tmp_path: Path):
    """R43 and R45 should PASS if skill exists and .agents/skills/ is compliant."""
    # R43 setup
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Tech Researcher Skill")

    # R45 setup (compliant)
    agents_skills = tmp_path / ".agents" / "skills"
    tech_fastapi = agents_skills / "tech-fastapi"
    tech_fastapi.mkdir(parents=True)
    (tech_fastapi / "SKILL.md").write_text("# FastAPI")

    results = check_tech_researcher(tmp_path)

    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_tech_researcher_missing_skill(tmp_path: Path):
    """R43 should FAIL if prothon-tech-researcher skill is missing."""
    # R45 setup (compliant)
    agents_skills = tmp_path / ".agents" / "skills"
    agents_skills.mkdir(parents=True)

    results = check_tech_researcher(tmp_path)

    r43 = next(r for r in results if r.requirement.requirement_id == "R43")
    assert r43.status == CheckStatus.FAIL
    assert "Missing prothon-tech-researcher skill" in r43.rationale


def test_check_tech_researcher_r45_naming_violations(tmp_path: Path):
    """R45 should FAIL if folder names are not kebab-case or SKILL.md is missing."""
    # R43 setup (pass)
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Tech Researcher Skill")

    # R45 setup (violations)
    agents_skills = tmp_path / ".agents" / "skills"
    (agents_skills / "tech_fastapi").mkdir(parents=True)  # snake_case
    (agents_skills / "tech-python").mkdir(parents=True)  # missing SKILL.md

    results = check_tech_researcher(tmp_path)

    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert "Folder 'tech_fastapi' is not kebab-case" in r45.rationale
    assert "Folder 'tech-python' is missing SKILL.md" in r45.rationale


def test_check_tech_researcher_r45_skip_no_tech_choices(tmp_path: Path):
    """R45 should SKIP if no tech choices in DESIGN.md and .agents/skills/ missing."""
    # R43 setup (pass)
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Tech Researcher Skill")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "DESIGN.md").write_text("# Design\n\nNo tech choices here.")

    results = check_tech_researcher(tmp_path)

    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.SKIP
    assert (
        "No technology choices in DESIGN.md and .agents/skills/ missing"
        in r45.rationale
    )


def test_check_tech_researcher_r45_fail_missing_dir_with_tech_choices(tmp_path: Path):
    """R45 should FAIL if DESIGN.md has tech choices but .agents/skills/ is missing."""
    # R43 setup (pass)
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Tech Researcher Skill")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "DESIGN.md").write_text(
        "# Design\n\n## Technology Choices\n\n- FastAPI"
    )

    results = check_tech_researcher(tmp_path)

    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert (
        "DESIGN.md has technology choices but .agents/skills/ is missing"
        in r45.rationale
    )


def test_check_tech_researcher_r45_fail_empty_dir_with_tech_choices(tmp_path: Path):
    """R45 should FAIL if DESIGN.md has tech choices but .agents/skills/ is empty."""
    # R43 setup (pass)
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Tech Researcher Skill")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "DESIGN.md").write_text(
        "# Design\n\n## Technology Choices\n\n- FastAPI"
    )

    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    results = check_tech_researcher(tmp_path)

    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert (
        "DESIGN.md has technology choices but .agents/skills/ is empty" in r45.rationale
    )
