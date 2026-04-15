"""Tests for compliance check functions: static checks, doc analysis, inheritance, etc."""

from __future__ import annotations

from pathlib import Path


from prothon.compliance import CheckStatus, CheckType, ComplianceReport
from prothon.checks import (
    analyze_python_file,
    check_agent_files,
    check_doc_existence,
    check_inheritance,
    check_patterns_doc,
    run_static_checks,
)


def test_analyze_python_file_valid(tmp_path: Path):
    """Test AST analysis of a valid Python file."""
    code = """
import os
from pathlib import Path
import sys as system

class MyBase:
    pass

class MyClass(MyBase, Path):
    def method(self):
        pass
"""
    file_path = tmp_path / "test_file.py"
    file_path.write_text(code)

    results = analyze_python_file(file_path)

    assert "os" in results["imports"]
    assert "pathlib" in results["imports"]
    assert "sys" in results["imports"]

    assert results["base_classes"]["MyBase"] == []
    assert results["base_classes"]["MyClass"] == ["MyBase", "Path"]


def test_analyze_python_file_missing(tmp_path: Path):
    """Test analysis of a missing file."""
    results = analyze_python_file(tmp_path / "nonexistent.py")
    assert results == {"imports": set(), "base_classes": {}}


def test_analyze_python_file_syntax_error(tmp_path: Path):
    """Test analysis of a file with syntax errors."""
    file_path = tmp_path / "bad.py"
    file_path.write_text("class MyClass:")  # Missing body

    results = analyze_python_file(file_path)
    assert results == {"imports": set(), "base_classes": {}}


def test_check_patterns_doc_missing(tmp_path: Path):
    """R25 and R26 should SKIP if PATTERNS.md is missing."""
    results = check_patterns_doc(tmp_path / "PATTERNS.md")
    assert len(results) == 2
    assert all(r.status == CheckStatus.SKIP for r in results)


def test_check_patterns_doc_valid(tmp_path: Path):
    """R25 and R26 should PASS for a valid PATTERNS.md."""
    content = """
# Patterns

This is some natural language rationale for the project.
It should be longer than the code blocks to pass R25.

```python
def my_function(arg: int) -> str:
    \"\"\"Docstring only.\"\"\"
    ...

class MyClass:
    def method(self):
        pass
```
"""
    patterns_path = tmp_path / "PATTERNS.md"
    patterns_path.write_text(content)

    results = check_patterns_doc(patterns_path)
    assert len(results) == 2
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_patterns_doc_code_dominant(tmp_path: Path):
    """R25 should FAIL if code blocks dominate the document."""
    # 70% threshold in code.
    # Let's make the code content very long compared to the text.
    code_content = "def func():\n" + "    pass\n" * 100
    code_block = f"```python\n{code_content}```\n"
    content = "Small text.\n" + code_block

    patterns_path = tmp_path / "PATTERNS.md"
    patterns_path.write_text(content)

    results = check_patterns_doc(patterns_path)
    r25 = next(r for r in results if r.requirement.requirement_id == "R25")
    assert r25.status == CheckStatus.FAIL
    assert "Code blocks dominate" in r25.rationale


def test_check_patterns_doc_non_signature(tmp_path: Path):
    """R26 should FAIL if code blocks contain implementation logic."""
    content = """
# Patterns

Rationale text.

```python
def my_function(arg: int) -> str:
    x = 1 + 1  # Implementation logic!
    return str(x)
```
"""
    patterns_path = tmp_path / "PATTERNS.md"
    patterns_path.write_text(content)

    results = check_patterns_doc(patterns_path)
    r26 = next(r for r in results if r.requirement.requirement_id == "R26")
    assert r26.status == CheckStatus.FAIL
    assert "contains implementation logic" in r26.rationale


def test_analyze_python_file_complex_bases(tmp_path: Path):
    """Test AST analysis with multiple and nested base class representations."""
    code = """
from abc import ABC

class A(ABC): pass
class B: pass
class C(A, B, list[int]): pass
"""
    file_path = tmp_path / "complex.py"
    file_path.write_text(code)

    results = analyze_python_file(file_path)
    assert results["base_classes"]["A"] == ["ABC"]
    assert results["base_classes"]["B"] == []
    # Note: list[int] might be unparsed or simplified depending on AST version/implementation
    assert "A" in results["base_classes"]["C"]
    assert "B" in results["base_classes"]["C"]


def test_check_patterns_doc_multiple_blocks_mixed(tmp_path: Path):
    """R26 should FAIL if even one of multiple blocks is invalid."""
    content = """
# Mixed Blocks

```python
def ok():
    ...
```

```python
def bad():
    print("Logic!")
```
"""
    patterns_path = tmp_path / "PATTERNS.md"
    patterns_path.write_text(content)

    results = check_patterns_doc(patterns_path)
    r26 = next(r for r in results if r.requirement.requirement_id == "R26")
    assert r26.status == CheckStatus.FAIL
    assert "bad():" in r26.evidence or "PATTERNS.md:9" in r26.evidence


def test_check_patterns_doc_exact_threshold(tmp_path: Path):
    """Test boundary behavior for the 70% code dominance threshold."""
    # 70% code vs 30% text.
    # Total length = 1000. Code = 700, Text = 300.
    # Let's adjust precisely.
    # Content inside ```python\n...``` is what counts as code_len.
    # Content including backticks is text_len.

    inner_code = "A" * 700
    code_block = f"```python\n{inner_code}```\n"
    # code_block length is 700 + 10 (backticks/newline) + 7 (python) = 717 approx.
    # If text is 200:
    text = "B" * 200
    content = text + code_block
    # text_len = 200 + 717 = 917.
    # code_len = 700.
    # 700 / 917 = 76% (Dominant)

    path = tmp_path / "THRESH.md"
    path.write_text(content)
    res = check_patterns_doc(path)
    r25 = next(r for r in res if r.requirement.requirement_id == "R25")
    assert r25.status == CheckStatus.FAIL


# --- check_doc_existence tests ---


def test_check_doc_existence_all_present(tmp_path: Path):
    """All three docs present should yield three PASS results."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for name in ("SPEC.md", "DESIGN.md", "PATTERNS.md"):
        (docs_dir / name).write_text("# Content")

    results = check_doc_existence(tmp_path)

    assert len(results) == 3
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_doc_existence_only_spec(tmp_path: Path):
    """Only SPEC.md present: SPEC PASS, DESIGN and PATTERNS FAIL."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "SPEC.md").write_text("# Spec")

    results = check_doc_existence(tmp_path)

    assert len(results) == 3
    spec, design, patterns = results
    assert spec.status == CheckStatus.PASS
    assert design.status == CheckStatus.FAIL
    assert patterns.status == CheckStatus.FAIL


def test_check_doc_existence_none_present(tmp_path: Path):
    """No docs present should yield three FAIL results."""
    # Don't even create the docs directory.
    results = check_doc_existence(tmp_path)

    assert len(results) == 3
    assert all(r.status == CheckStatus.FAIL for r in results)


# --- check_inheritance tests ---


def test_check_inheritance_all_inherit(tmp_path: Path):
    """All exceptions inheriting ProthonError should PASS."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\n"
        "class ConfigError(ProthonError): pass\n"
        "class ParseError(ProthonError): pass\n"
    )

    results = check_inheritance(tmp_path)

    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_check_inheritance_violation(tmp_path: Path):
    """An exception not inheriting ProthonError should FAIL with its name."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\n"
        "class GoodError(ProthonError): pass\n"
        "class BadError(ValueError): pass\n"
    )

    results = check_inheritance(tmp_path)

    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "BadError" in results[0].rationale


def test_check_inheritance_no_exceptions_file(tmp_path: Path):
    """Missing exceptions.py should return empty results."""
    results = check_inheritance(tmp_path)

    assert results == []


# --- check_agent_files tests ---


def test_check_agent_files_all_valid(tmp_path: Path):
    """AGENTS.md present with valid symlinks for CLAUDE/GEMINI/AGENT → all PASS."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")

    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(agents)

    results = check_agent_files(tmp_path)

    assert len(results) == 4
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_agent_files_agents_md_missing(tmp_path: Path):
    """Missing AGENTS.md means all four checks FAIL (symlinks also broken)."""
    results = check_agent_files(tmp_path)

    assert len(results) == 4
    assert all(r.status == CheckStatus.FAIL for r in results)


def test_check_agent_files_regular_files_not_symlinks(tmp_path: Path):
    """Symlink files that are regular files (not symlinks) should FAIL."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")

    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).write_text("# Not a symlink")

    results = check_agent_files(tmp_path)

    assert len(results) == 4
    # AGENTS.md itself should PASS
    agents_result = results[0]
    assert agents_result.status == CheckStatus.PASS

    # The three symlink files should FAIL with "must be a symlink" rationale
    for r in results[1:]:
        assert r.status == CheckStatus.FAIL
        assert "must be a symlink" in r.rationale


def test_check_agent_files_wrong_symlink_target(tmp_path: Path):
    """Symlinks pointing to wrong target should FAIL."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")

    wrong_target = tmp_path / "OTHER.md"
    wrong_target.write_text("# Wrong")

    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(wrong_target)

    results = check_agent_files(tmp_path)

    assert len(results) == 4
    assert results[0].status == CheckStatus.PASS  # AGENTS.md itself

    for r in results[1:]:
        assert r.status == CheckStatus.FAIL
        assert "symlink points to" in r.rationale


# --- run_static_checks tests ---


def test_run_static_checks_minimal_compliant(tmp_path: Path):
    """A minimal compliant project should return a ComplianceReport with all STATIC."""
    # docs with SPEC, DESIGN, PATTERNS
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "SPEC.md").write_text("# Spec\n\nRequirements here.")
    (docs_dir / "DESIGN.md").write_text("# Design\n\nArchitecture here.")
    patterns_content = (
        "# Patterns\n\n"
        "Rationale text that is longer than the code block content.\n"
        "More rationale to ensure text dominates over code.\n\n"
        "```python\n"
        "def example():\n"
        '    """Docstring only."""\n'
        "    ...\n"
        "```\n"
    )
    (docs_dir / "PATTERNS.md").write_text(patterns_content)

    # exceptions.py with ProthonError
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text("class ProthonError(Exception): pass\n")

    # AGENTS.md + symlinks
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        (tmp_path / name).symlink_to(agents)

    report = run_static_checks(tmp_path)

    assert isinstance(report, ComplianceReport)
    assert len(report.results) > 0
    assert all(r.check_type == CheckType.STATIC for r in report.results)


# --- check_package_structure tests (from test_compliance_impl.py) ---


def test_check_package_structure_missing_src(tmp_path: Path):
    """Test check_package_structure when src/ is missing."""
    from prothon.checks import check_package_structure

    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing src/ directory" in results[0].rationale


def test_check_package_structure_no_package(tmp_path: Path):
    """Test check_package_structure when src/ exists but no package is found."""
    from prothon.checks import check_package_structure

    (tmp_path / "src").mkdir()
    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "No Python packages found in src/" in results[0].rationale


def test_check_package_structure_missing_py_typed(tmp_path: Path):
    """Test check_package_structure when py.typed is missing from the package."""
    from prothon.checks import check_package_structure

    pkg_dir = tmp_path / "src" / "my_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")

    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing py.typed marker" in results[0].rationale


def test_check_package_structure_compliant(tmp_path: Path):
    """Test check_package_structure with a compliant layout."""
    from prothon.checks import check_package_structure

    pkg_dir = tmp_path / "src" / "my_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "py.typed").write_text("")

    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


# --- check_pre_commit tests ---


def test_check_pre_commit_missing(tmp_path: Path):
    """Test check_pre_commit when the config file is missing."""
    from prothon.checks import check_pre_commit

    results = check_pre_commit(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing pre-commit config" in results[0].rationale


def test_check_pre_commit_compliant(tmp_path: Path):
    """Test check_pre_commit when the config file exists."""
    from prothon.checks import check_pre_commit

    (tmp_path / ".pre-commit-config.yaml").write_text("")
    results = check_pre_commit(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


# --- check_skills_dir tests ---


def test_check_skills_dir_missing(tmp_path: Path):
    """Test check_skills_dir when the directory is missing."""
    from prothon.checks import check_skills_dir

    results = check_skills_dir(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing project skills directory" in results[0].rationale


def test_check_skills_dir_compliant(tmp_path: Path):
    """Test check_skills_dir when the directory exists."""
    from prothon.checks import check_skills_dir

    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    results = check_skills_dir(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS
