"""Unit tests for the prothon.checks subpackage.

Covers simple single-function checks: analyze_python_file, check_patterns_doc,
check_doc_existence, check_doc_harmonizer, check_package_structure,
check_pre_commit, check_skills_dir, check_agent_files, and check_inheritance.
"""

from __future__ import annotations

from pathlib import Path

from prothon.checks import (
    analyze_python_file,
    check_agent_files,
    check_doc_existence,
    check_doc_harmonizer,
    check_inheritance,
    check_package_structure,
    check_patterns_doc,
    check_pre_commit,
    check_skills_dir,
)
from prothon.compliance import CheckStatus


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
