"""Tests for the prothon.checks subpackage.

Covers all public check_* functions and key utilities with both PASS and FAIL
scenarios, using tmp_path to create minimal project structures.
"""

from __future__ import annotations

from pathlib import Path

from prothon.checks import (
    analyze_python_file,
    check_adoption_intelligence,
    check_agent_files,
    check_doc_existence,
    check_doc_harmonizer,
    check_execute_logic,
    check_inheritance,
    check_package_structure,
    check_patterns_doc,
    check_pre_commit,
    check_refactor_logic,
    check_semantic_versioning,
    check_skills_dir,
    check_tech_researcher,
    run_static_checks,
)
from prothon.compliance import CheckStatus, CheckType, ComplianceReport


# ---------------------------------------------------------------------------
# analyze_python_file
# ---------------------------------------------------------------------------


def test_analyze_python_file_collects_imports(tmp_path: Path) -> None:
    """analyze_python_file returns all import and from-import module names."""
    code = "import os\nfrom pathlib import Path\nimport json\n"
    f = tmp_path / "mod.py"
    f.write_text(code)
    result = analyze_python_file(f)
    assert {"os", "pathlib", "json"} <= result["imports"]


def test_analyze_python_file_collects_base_classes(tmp_path: Path) -> None:
    """analyze_python_file maps class names to their base class names."""
    code = "class A: pass\nclass B(A): pass\n"
    f = tmp_path / "mod.py"
    f.write_text(code)
    result = analyze_python_file(f)
    assert result["base_classes"]["A"] == []
    assert result["base_classes"]["B"] == ["A"]


def test_analyze_python_file_missing_returns_empty(tmp_path: Path) -> None:
    """analyze_python_file returns empty sets/dicts for a missing file."""
    result = analyze_python_file(tmp_path / "nope.py")
    assert result == {"imports": set(), "base_classes": {}}


def test_analyze_python_file_syntax_error_returns_empty(tmp_path: Path) -> None:
    """analyze_python_file returns empty sets/dicts for unparseable code."""
    f = tmp_path / "bad.py"
    f.write_text("def (broken syntax")
    result = analyze_python_file(f)
    assert result == {"imports": set(), "base_classes": {}}


# ---------------------------------------------------------------------------
# check_patterns_doc
# ---------------------------------------------------------------------------


def test_check_patterns_doc_missing_skips(tmp_path: Path) -> None:
    """Both R25 and R26 SKIP when PATTERNS.md does not exist."""
    results = check_patterns_doc(tmp_path / "PATTERNS.md")
    assert len(results) == 2
    assert all(r.status == CheckStatus.SKIP for r in results)


def test_check_patterns_doc_no_code_blocks_passes(tmp_path: Path) -> None:
    """Both R25 and R26 PASS when PATTERNS.md has no python code blocks."""
    p = tmp_path / "PATTERNS.md"
    p.write_text("# Patterns\n\nAll natural language, no code.\n")
    results = check_patterns_doc(p)
    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_patterns_doc_signature_only_passes(tmp_path: Path) -> None:
    """R25 and R26 PASS when code blocks contain only signatures."""
    content = (
        "# Patterns\n\n"
        "This is a long description of the patterns used in this project. "
        "It has lots of natural language to stay below the 70 percent threshold.\n\n"
        "```python\n"
        "def example(arg: int) -> str:\n"
        '    """Signature only."""\n'
        "    ...\n"
        "```\n"
    )
    p = tmp_path / "PATTERNS.md"
    p.write_text(content)
    results = check_patterns_doc(p)
    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_patterns_doc_code_dominant_fails_r25(tmp_path: Path) -> None:
    """R25 FAIL when code blocks exceed 70 percent of content."""
    code_body = "def f():\n" + "    pass\n" * 100
    content = "Short.\n```python\n" + code_body + "```\n"
    p = tmp_path / "PATTERNS.md"
    p.write_text(content)
    results = check_patterns_doc(p)
    r25 = next(r for r in results if r.requirement.requirement_id == "R25")
    assert r25.status == CheckStatus.FAIL


def test_check_patterns_doc_implementation_fails_r26(tmp_path: Path) -> None:
    """R26 FAIL when a code block has implementation logic."""
    content = (
        "# Patterns\n\nRationale here.\n\n"
        "```python\n"
        "def compute(x: int) -> int:\n"
        "    return x * 2\n"
        "```\n"
    )
    p = tmp_path / "PATTERNS.md"
    p.write_text(content)
    results = check_patterns_doc(p)
    r26 = next(r for r in results if r.requirement.requirement_id == "R26")
    assert r26.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_doc_existence
# ---------------------------------------------------------------------------


def test_check_doc_existence_all_present(tmp_path: Path) -> None:
    """All three docs present yields three PASS results."""
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("SPEC.md", "DESIGN.md", "PATTERNS.md"):
        (docs / name).write_text("# Title")
    results = check_doc_existence(tmp_path)
    assert len(results) == 3
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_doc_existence_none_present(tmp_path: Path) -> None:
    """No docs present yields three FAIL results."""
    results = check_doc_existence(tmp_path)
    assert len(results) == 3
    assert all(r.status == CheckStatus.FAIL for r in results)


def test_check_doc_existence_partial(tmp_path: Path) -> None:
    """Only SPEC.md present: one PASS, two FAIL."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec")
    results = check_doc_existence(tmp_path)
    statuses = [r.status for r in results]
    assert statuses.count(CheckStatus.PASS) == 1
    assert statuses.count(CheckStatus.FAIL) == 2


# ---------------------------------------------------------------------------
# check_doc_harmonizer
# ---------------------------------------------------------------------------


def test_check_doc_harmonizer_skill_present(tmp_path: Path) -> None:
    """PASS when prothon-doc-harmonizer SKILL.md exists."""
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-doc-harmonizer"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Doc Harmonizer")
    results = check_doc_harmonizer(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_doc_harmonizer_skill_missing(tmp_path: Path) -> None:
    """FAIL when prothon-doc-harmonizer SKILL.md is absent."""
    results = check_doc_harmonizer(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing" in results[0].rationale


# ---------------------------------------------------------------------------
# check_package_structure
# ---------------------------------------------------------------------------


def test_check_package_structure_compliant(tmp_path: Path) -> None:
    """PASS when src/<pkg>/__init__.py and py.typed exist."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "py.typed").write_text("")
    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_package_structure_no_src(tmp_path: Path) -> None:
    """FAIL when src/ directory is missing."""
    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing src/" in results[0].rationale


def test_check_package_structure_no_package(tmp_path: Path) -> None:
    """FAIL when src/ exists but contains no Python package."""
    (tmp_path / "src").mkdir()
    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "No Python packages" in results[0].rationale


def test_check_package_structure_missing_py_typed(tmp_path: Path) -> None:
    """FAIL when package exists but py.typed marker is absent."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing py.typed" in results[0].rationale


# ---------------------------------------------------------------------------
# check_pre_commit
# ---------------------------------------------------------------------------


def test_check_pre_commit_present(tmp_path: Path) -> None:
    """PASS when .pre-commit-config.yaml exists."""
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []")
    results = check_pre_commit(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_pre_commit_missing(tmp_path: Path) -> None:
    """FAIL when .pre-commit-config.yaml is absent."""
    results = check_pre_commit(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_skills_dir
# ---------------------------------------------------------------------------


def test_check_skills_dir_present(tmp_path: Path) -> None:
    """PASS when .agents/skills/ directory exists."""
    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    results = check_skills_dir(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_skills_dir_missing(tmp_path: Path) -> None:
    """FAIL when .agents/skills/ directory is absent."""
    results = check_skills_dir(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_agent_files
# ---------------------------------------------------------------------------


def test_check_agent_files_all_valid(tmp_path: Path) -> None:
    """PASS for AGENTS.md plus three correct symlinks."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(agents)
    results = check_agent_files(tmp_path)
    assert len(results) == 4
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_agent_files_all_missing(tmp_path: Path) -> None:
    """FAIL for all four when nothing exists."""
    results = check_agent_files(tmp_path)
    assert len(results) == 4
    assert all(r.status == CheckStatus.FAIL for r in results)


def test_check_agent_files_regular_not_symlink(tmp_path: Path) -> None:
    """FAIL when CLAUDE.md etc. are regular files, not symlinks."""
    (tmp_path / "AGENTS.md").write_text("# Agents")
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).write_text("regular file")
    results = check_agent_files(tmp_path)
    agents_result = results[0]
    assert agents_result.status == CheckStatus.PASS
    for r in results[1:]:
        assert r.status == CheckStatus.FAIL
        assert "must be a symlink" in r.rationale


def test_check_agent_files_wrong_symlink_target(tmp_path: Path) -> None:
    """FAIL when symlinks point to the wrong file."""
    (tmp_path / "AGENTS.md").write_text("# Agents")
    wrong = tmp_path / "OTHER.md"
    wrong.write_text("wrong")
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(wrong)
    results = check_agent_files(tmp_path)
    assert results[0].status == CheckStatus.PASS
    for r in results[1:]:
        assert r.status == CheckStatus.FAIL
        assert "symlink points to" in r.rationale


# ---------------------------------------------------------------------------
# check_inheritance
# ---------------------------------------------------------------------------


def test_check_inheritance_all_valid(tmp_path: Path) -> None:
    """PASS when all exceptions inherit from ProthonError."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\nclass FooError(ProthonError): pass\n"
    )
    results = check_inheritance(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_inheritance_violation(tmp_path: Path) -> None:
    """FAIL when an exception does not inherit from ProthonError."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\nclass BadError(ValueError): pass\n"
    )
    results = check_inheritance(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "BadError" in results[0].rationale


def test_check_inheritance_no_file(tmp_path: Path) -> None:
    """Empty results when exceptions.py does not exist."""
    results = check_inheritance(tmp_path)
    assert results == []


# ---------------------------------------------------------------------------
# check_execute_logic
# ---------------------------------------------------------------------------


def test_check_execute_logic_all_present(tmp_path: Path) -> None:
    """PASS results when promise.py, promise_verify.py, and execute skill exist."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)

    # promise.py with plan function and task fields
    (prothon / "promise.py").write_text(
        "def plan():\n    pass\nexpected_lines_added = 0\nfiles_to_modify = []\n"
    )

    # promise_verify.py with check_task and actual_added
    (prothon / "promise_verify.py").write_text(
        "def check_task():\n    actual_added = 0\n"
    )

    # execute skill
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
    """Empty results when none of the expected files exist."""
    results = check_execute_logic(tmp_path)
    assert results == []


def test_check_execute_logic_partial(tmp_path: Path) -> None:
    """Only promise.py present yields partial results."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "promise.py").write_text(
        "def plan():\n    pass\nexpected_lines_added = 0\nfiles_to_modify = []\n"
    )
    results = check_execute_logic(tmp_path)
    # Should have R27 and R28 but not R30/R31/R32/R33
    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


# ---------------------------------------------------------------------------
# check_refactor_logic
# ---------------------------------------------------------------------------


def test_check_refactor_logic_all_present(tmp_path: Path) -> None:
    """PASS results when refactor.py and refactor skill exist with keywords."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "refactor.py").write_text("# refactor module\n")

    skill_dir = prothon / "skills" / "prothon-refactor"
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
    """FAIL for R38 when refactor.py and skill are missing."""
    results = check_refactor_logic(tmp_path)
    assert len(results) == 1
    assert results[0].requirement.requirement_id == "R38"
    assert results[0].status == CheckStatus.FAIL


def test_check_refactor_logic_only_module(tmp_path: Path) -> None:
    """Only R38 PASS when refactor.py exists but skill is absent."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "refactor.py").write_text("# refactor\n")
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
    # Also need .agents/skills with a kebab-case folder
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
    # tech-researcher skill exists
    skill = tmp_path / "src" / "prothon" / "skills" / "prothon-tech-researcher"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Researcher")

    # .agents/skills with valid folders
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
    (skills_dir / "tech-ruff").mkdir()  # no SKILL.md

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
    # Missing version-tag and gitlab templates
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
    # Create docs
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("SPEC.md", "DESIGN.md"):
        (docs / name).write_text("# Title")
    (docs / "PATTERNS.md").write_text("# Patterns\nNatural language content here.\n")

    # Create package structure
    pkg = tmp_path / "src" / "prothon"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "py.typed").write_text("")
    (pkg / "exceptions.py").write_text("class ProthonError(Exception): pass\n")

    # Agent files
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(agents)

    # Pre-commit
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []")

    # Skills dir
    (tmp_path / ".agents" / "skills").mkdir(parents=True)

    report = run_static_checks(tmp_path)
    passes = [r for r in report.results if r.status == CheckStatus.PASS]
    assert len(passes) > 0
