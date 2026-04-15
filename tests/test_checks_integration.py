"""Integration tests for prothon.checks -- complex multi-component checks and orchestration.

Tests checks that require elaborate project setup with multiple interacting
components: execute logic, refactor logic, tech researcher, semantic versioning,
adoption intelligence, and the full run_static_checks orchestrator.
"""

from __future__ import annotations

from pathlib import Path

from prothon.checks import (
    check_adoption_intelligence,
    check_execute_logic,
    check_refactor_logic,
    check_semantic_versioning,
    check_tech_researcher,
    run_static_checks,
)
from prothon.compliance import CheckStatus, CheckType, ComplianceReport


# ---------------------------------------------------------------------------
# check_execute_logic
# ---------------------------------------------------------------------------


def test_check_execute_logic_all_present(tmp_path: Path) -> None:
    """PASS results when promise.py, promise_verify.py, and execute skill exist."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)

    (prothon / "promise.py").write_text(
        "def plan():\n    pass\nexpected_lines_added = 0\nfiles_to_modify = []\n"
    )

    (prothon / "promise_verify.py").write_text(
        "def check_task():\n    actual_added = 0\n"
    )

    skill_dir = prothon / "skills" / "prothon-execute"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Execute\n"
        "Fresh instances for fresh-context subagent loops.\n"
        "Run pre-commit hooks.\n"
        "Use record-attempt for retries.\n"
    )

    results = check_execute_logic(tmp_path)
    assert len(results) >= 3
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_execute_logic_nothing_present(tmp_path: Path) -> None:
    """SKIP results for promise.py checks when file missing; empty for others."""
    results = check_execute_logic(tmp_path)
    assert len(results) == 2
    assert all(r.status == CheckStatus.SKIP for r in results)
    assert all("promise.py" in r.rationale for r in results)


def test_check_execute_logic_partial(tmp_path: Path) -> None:
    """Only promise.py present yields partial results."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "promise.py").write_text(
        "def plan():\n    pass\nexpected_lines_added = 0\nfiles_to_modify = []\n"
    )
    results = check_execute_logic(tmp_path)
    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


# ---------------------------------------------------------------------------
# check_refactor_logic
# ---------------------------------------------------------------------------


def test_check_refactor_logic_all_present(tmp_path: Path) -> None:
    """PASS results when refactor subpackage and refactor skill exist with keywords."""
    refactor_dir = tmp_path / "src" / "prothon" / "refactor"
    refactor_dir.mkdir(parents=True)
    (refactor_dir / "__init__.py").write_text("# refactor subpackage\n")

    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-refactor"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Refactor\n"
        "DESIGN -> PATTERNS -> CODE\n"
        "Phase 1: Interactive Discovery\n"
        "Phase 2: Execution with subagent loops\n"
        "Each task must reference the specific documentation heading.\n"
    )

    results = check_refactor_logic(tmp_path)
    assert len(results) == 5
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_refactor_logic_nothing_present(tmp_path: Path) -> None:
    """FAIL for R38 when refactor subpackage and skill are missing."""
    results = check_refactor_logic(tmp_path)
    assert len(results) == 1
    assert results[0].requirement.requirement_id == "R38"
    assert results[0].status == CheckStatus.FAIL


def test_check_refactor_logic_only_module(tmp_path: Path) -> None:
    """Only R38 PASS when refactor subpackage exists but skill is absent."""
    refactor_dir = tmp_path / "src" / "prothon" / "refactor"
    refactor_dir.mkdir(parents=True)
    (refactor_dir / "__init__.py").write_text("# refactor\n")
    results = check_refactor_logic(tmp_path)
    assert len(results) == 1
    req_ids = [r.requirement.requirement_id for r in results]
    assert "R38" in req_ids


# ---------------------------------------------------------------------------
# check_tech_researcher
# ---------------------------------------------------------------------------


def test_check_tech_researcher_skill_present(tmp_path: Path) -> None:
    """R43 PASS when prothon-tech-researcher SKILL.md exists."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Tech Researcher")
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    sub = skills_dir / "tech-pytest"
    sub.mkdir()
    (sub / "SKILL.md").write_text("# Skill")

    results = check_tech_researcher(tmp_path)
    r43 = next(r for r in results if r.requirement.requirement_id == "R43")
    assert r43.status == CheckStatus.PASS


def test_check_tech_researcher_skill_missing(tmp_path: Path) -> None:
    """R43 FAIL when prothon-tech-researcher SKILL.md is absent."""
    results = check_tech_researcher(tmp_path)
    r43 = next(r for r in results if r.requirement.requirement_id == "R43")
    assert r43.status == CheckStatus.FAIL


def test_check_tech_researcher_reference_skills_kebab(tmp_path: Path) -> None:
    """R45 PASS with kebab-case skill folders containing SKILL.md."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    for name in ("tech-ruff", "style-black"):
        d = skills_dir / name
        d.mkdir()
        (d / "SKILL.md").write_text("# Skill")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.PASS


def test_check_tech_researcher_non_kebab_folder_fails(tmp_path: Path) -> None:
    """R45 FAIL with a non-kebab-case folder in .agents/skills/."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    bad = skills_dir / "NotKebab"
    bad.mkdir()
    (bad / "SKILL.md").write_text("# Bad")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert "not kebab-case" in r45.rationale


def test_check_tech_researcher_missing_skill_md_in_folder(tmp_path: Path) -> None:
    """R45 FAIL when a skills folder is missing SKILL.md."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "tech-ruff").mkdir()

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL
    assert "missing SKILL.md" in r45.rationale


def test_check_tech_researcher_no_skills_dir_with_tech_choices(
    tmp_path: Path,
) -> None:
    """R45 FAIL when DESIGN.md has tech choices but .agents/skills/ missing."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "DESIGN.md").write_text("# Design\n## Technology Choices\nPython 3.12\n")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.FAIL


def test_check_tech_researcher_no_skills_dir_no_tech_choices(
    tmp_path: Path,
) -> None:
    """R45 SKIP when no tech choices and no .agents/skills/."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    results = check_tech_researcher(tmp_path)
    r45 = next(r for r in results if r.requirement.requirement_id == "R45")
    assert r45.status == CheckStatus.SKIP


# ---------------------------------------------------------------------------
# check_semantic_versioning
# ---------------------------------------------------------------------------


def test_check_semantic_versioning_all_templates(tmp_path: Path) -> None:
    """R53 and R55 PASS when all CI workflow templates exist."""
    gh = tmp_path / "template" / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-bump.yml.jinja").write_text("")
    (gh / "version-tag.yml.jinja").write_text("")
    (tmp_path / "template" / ".gitlab-ci.yml.jinja").write_text("")

    results = check_semantic_versioning(tmp_path)
    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_semantic_versioning_missing_templates(tmp_path: Path) -> None:
    """R53 and R55 FAIL when templates are missing."""
    results = check_semantic_versioning(tmp_path)
    assert len(results) == 2
    assert all(r.status == CheckStatus.FAIL for r in results)


def test_check_semantic_versioning_partial_templates(tmp_path: Path) -> None:
    """R53 and R55 FAIL when only some templates exist."""
    gh = tmp_path / "template" / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "version-bump.yml.jinja").write_text("")
    results = check_semantic_versioning(tmp_path)
    assert len(results) == 2
    assert all(r.status == CheckStatus.FAIL for r in results)


# ---------------------------------------------------------------------------
# check_adoption_intelligence
# ---------------------------------------------------------------------------


def test_check_adoption_intelligence_pass(tmp_path: Path) -> None:
    """R13 PASS when ast_miner.py exists and adoption.py imports and uses it."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner:\n    pass\n")
    (prothon / "adoption.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner\nminer = ASTPatternMiner()\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_adoption_intelligence_no_miner(tmp_path: Path) -> None:
    """R13 FAIL when ast_miner.py does not exist."""
    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing ASTPatternMiner" in results[0].rationale


def test_check_adoption_intelligence_no_import(tmp_path: Path) -> None:
    """R13 FAIL when adoption.py does not import ast_miner."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "adoption.py").write_text("# empty adoption\n")

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "does not import" in results[0].rationale


def test_check_adoption_intelligence_no_usage(tmp_path: Path) -> None:
    """R13 FAIL when adoption.py imports but does not instantiate ASTPatternMiner."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "adoption.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner\n# imported but never called\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "does not appear to use" in results[0].rationale


def test_check_adoption_intelligence_falls_back_to_scaffold(
    tmp_path: Path,
) -> None:
    """R13 PASS when adoption.py is absent but scaffold.py has the import+usage."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "scaffold.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner\nm = ASTPatternMiner()\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_adoption_intelligence_from_import_attribute_call(
    tmp_path: Path,
) -> None:
    """R13 PASS with `from prothon import ast_miner; ast_miner.ASTPatternMiner()`."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "adoption.py").write_text(
        "from prothon import ast_miner\nm = ast_miner.ASTPatternMiner()\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_adoption_intelligence_aliased_module_call(
    tmp_path: Path,
) -> None:
    """R13 PASS with `import prothon.ast_miner as am; am.ASTPatternMiner(x)`."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "adoption.py").write_text(
        "import prothon.ast_miner as am\nm = am.ASTPatternMiner(42)\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_adoption_intelligence_direct_from_import(
    tmp_path: Path,
) -> None:
    """R13 PASS with `from prothon.ast_miner import ASTPatternMiner; ASTPatternMiner()`."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "adoption.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner\nm = ASTPatternMiner()\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_adoption_intelligence_aliased_class_call(
    tmp_path: Path,
) -> None:
    """R13 PASS with `from prothon.ast_miner import ASTPatternMiner as Miner; Miner()`."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (prothon / "adoption.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner as Miner\nm = Miner()\n"
    )

    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# run_static_checks
# ---------------------------------------------------------------------------


def test_run_static_checks_returns_report(tmp_path: Path) -> None:
    """run_static_checks returns a ComplianceReport with all STATIC results."""
    report = run_static_checks(tmp_path)
    assert isinstance(report, ComplianceReport)
    assert len(report.results) > 0
    assert all(r.check_type == CheckType.STATIC for r in report.results)


def test_run_static_checks_minimal_compliant_project(tmp_path: Path) -> None:
    """A minimal project with docs and structure produces some PASS results."""
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("SPEC.md", "DESIGN.md"):
        (docs / name).write_text("# Title")
    (docs / "PATTERNS.md").write_text("# Patterns\nNatural language content here.\n")

    pkg = tmp_path / "src" / "prothon"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "py.typed").write_text("")
    (pkg / "exceptions.py").write_text("class ProthonError(Exception): pass\n")

    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(agents)

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []")

    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    report = run_static_checks(tmp_path)
    passes = [r for r in report.results if r.status == CheckStatus.PASS]
    assert len(passes) > 0
