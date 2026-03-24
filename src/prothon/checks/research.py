from __future__ import annotations

import re
from pathlib import Path

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


def check_tech_researcher(root: Path) -> list[CheckResult]:
    """Verify Tech-Researcher implementation (SPEC R43-R46)."""
    results = []
    r43 = Requirement(
        source="SPEC",
        requirement_id="R43",
        statement="System must automatically generate reference skills based on technology choices.",
    )
    r45 = Requirement(
        source="SPEC",
        requirement_id="R45",
        statement="Reference skills must be stored in .agents/skills/ using kebab-case and SKILL.md.",
    )

    results.append(_check_tech_researcher_skill_existence(root, r43))
    results.extend(_check_reference_skills_storage(root, r45))

    return results


def _check_tech_researcher_skill_existence(root: Path, r43: Requirement) -> CheckResult:
    skill_path = (
        root / "src" / "prothon" / "skills" / "prothon-tech-researcher" / "SKILL.md"
    )
    if skill_path.exists():
        return CheckResult(
            requirement=r43, status=CheckStatus.PASS, evidence=str(skill_path)
        )
    return CheckResult(
        requirement=r43,
        status=CheckStatus.FAIL,
        evidence=str(skill_path),
        rationale="Missing prothon-tech-researcher skill.",
    )


def _has_tech_choices(design_path: Path) -> bool:
    if design_path.exists():
        content = design_path.read_text()
        if "Technology Choices" in content or "Key Decisions" in content:
            return True
    return False


def _verify_skill_folders(
    skill_folders: list[Path], skills_dir: Path, r45: Requirement
) -> list[CheckResult]:
    kebab_pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    violations = []

    for folder in skill_folders:
        if not kebab_pattern.match(folder.name):
            violations.append(f"Folder '{folder.name}' is not kebab-case.")
        if not (folder / "SKILL.md").exists():
            violations.append(f"Folder '{folder.name}' is missing SKILL.md.")

    if violations:
        return [
            CheckResult(
                requirement=r45,
                status=CheckStatus.FAIL,
                evidence=str(skills_dir),
                rationale="; ".join(violations),
            )
        ]
    return [
        CheckResult(requirement=r45, status=CheckStatus.PASS, evidence=str(skills_dir))
    ]


def _check_reference_skills_storage(root: Path, r45: Requirement) -> list[CheckResult]:
    design_path = root / "docs" / "DESIGN.md"
    skills_dir = root / ".agents" / "skills"
    has_tech = _has_tech_choices(design_path)

    if not skills_dir.exists():
        if has_tech:
            return [
                CheckResult(
                    requirement=r45,
                    status=CheckStatus.FAIL,
                    evidence=str(skills_dir),
                    rationale="DESIGN.md has technology choices but .agents/skills/ is missing.",
                )
            ]
        return [
            CheckResult(
                requirement=r45,
                status=CheckStatus.SKIP,
                rationale="No technology choices in DESIGN.md and .agents/skills/ missing.",
            )
        ]

    # Check skills directory content
    skill_folders = [d for d in skills_dir.iterdir() if d.is_dir()]
    if not skill_folders:
        if has_tech:
            return [
                CheckResult(
                    requirement=r45,
                    status=CheckStatus.FAIL,
                    evidence=str(skills_dir),
                    rationale="DESIGN.md has technology choices but .agents/skills/ is empty.",
                )
            ]
        return [
            CheckResult(
                requirement=r45,
                status=CheckStatus.PASS,
                evidence=str(skills_dir),
                rationale=".agents/skills/ exists and is empty (no tech choices expected).",
            )
        ]

    return _verify_skill_folders(skill_folders, skills_dir, r45)


def check_semantic_versioning(root: Path) -> list[CheckResult]:
    """Verify Semantic Versioning CI workflows (SPEC R53, R55)."""
    results = []

    r53 = Requirement(
        source="SPEC",
        requirement_id="R53",
        statement="Scaffolded projects (prothon new) must include CI workflows that detect change types and perform version bumps.",
    )
    r55 = Requirement(
        source="SPEC",
        requirement_id="R55",
        statement="The version bump CI workflow must be included for both GitHub Actions and GitLab CI/CD.",
    )

    templates = [
        (
            root / "template" / ".github" / "workflows" / "version-bump.yml.jinja",
            "GitHub Actions version bump",
        ),
        (
            root / "template" / ".github" / "workflows" / "version-tag.yml.jinja",
            "GitHub Actions version tag",
        ),
        (root / "template" / ".gitlab-ci.yml.jinja", "GitLab CI/CD version bump"),
    ]

    missing = [str(p) for p, _ in templates if not p.exists()]
    evidence = ", ".join(str(p) for p, _ in templates if p.exists())

    if missing:
        rationale = f"Missing CI workflow templates: {', '.join(missing)}"
        results.append(CheckResult(r53, CheckStatus.FAIL, rationale=rationale))
        results.append(CheckResult(r55, CheckStatus.FAIL, rationale=rationale))
    else:
        results.append(CheckResult(r53, CheckStatus.PASS, evidence=evidence))
        results.append(CheckResult(r55, CheckStatus.PASS, evidence=evidence))

    return results
