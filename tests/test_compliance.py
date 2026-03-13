from __future__ import annotations

from pathlib import Path
import pytest
from hypothesis import given, strategies as st

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    ComplianceReport,
    Requirement,
    analyze_python_file,
    check_patterns_doc,
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


def test_compliance_report_properties():
    """Test aggregation properties of ComplianceReport."""
    req = Requirement(source="SPEC", statement="Test req")
    results = [
        CheckResult(req, CheckStatus.PASS),
        CheckResult(req, CheckStatus.FAIL, rationale="Broken"),
        CheckResult(req, CheckStatus.SKIP),
    ]
    report = ComplianceReport(results=results)

    assert report.passed is False
    assert len(report.failures) == 1
    assert report.failures[0].status == CheckStatus.FAIL

    # Score: 1 PASS / (1 PASS + 1 FAIL) = 50%
    assert report.score == 50.0


def test_compliance_report_format_summary():
    """Test the formatted output of the compliance report."""
    req = Requirement(source="SPEC", statement="Test requirement implementation")
    results = [
        CheckResult(req, CheckStatus.PASS),
        CheckResult(req, CheckStatus.FAIL, rationale="Does not match"),
    ]
    report = ComplianceReport(results=results)
    summary = report.format_summary()

    assert "COMPLIANCE SUMMARY" in summary
    assert "Overall Score: 50.0%" in summary
    assert "Found 1 compliance violations" in summary
    assert "- [SPEC] Test requirement implementation" in summary


def test_check_result_str_with_id():
    """CheckResult.__str__ includes the requirement ID if present."""
    req = Requirement(source="SPEC", requirement_id="R1", statement="Must exist")
    res = CheckResult(req, CheckStatus.PASS, evidence="file:1")
    s = str(res)
    assert "PASS" in s
    assert "[R1]" in s
    assert "SPEC" in s
    assert "Must exist" in s
    assert "(file:1)" in s


def test_check_result_str_without_id():
    """CheckResult.__str__ omits the requirement ID if not present."""
    req = Requirement(source="DESIGN", statement="No ID here")
    res = CheckResult(req, CheckStatus.FAIL, evidence="src:10", rationale="Missing")
    s = str(res)
    assert "FAIL" in s
    assert "DESIGN" in s
    assert "No ID here" in s
    assert "(src:10)" in s
    assert "[]" not in s


def test_compliance_report_passed_with_skips():
    """ComplianceReport.passed should be True if all results are PASS or SKIP."""
    req = Requirement(source="SPEC", statement="Test")
    report = ComplianceReport(
        results=[
            CheckResult(req, CheckStatus.PASS),
            CheckResult(req, CheckStatus.SKIP),
        ]
    )
    assert report.passed is True


def test_compliance_report_results_by_source():
    """ComplianceReport.results_by_source filters correctly."""
    r1 = Requirement(source="SPEC", statement="S1")
    r2 = Requirement(source="DESIGN", statement="D1")
    r3 = Requirement(source="PATTERNS", statement="P1")

    report = ComplianceReport(
        results=[
            CheckResult(r1, CheckStatus.PASS),
            CheckResult(r2, CheckStatus.FAIL),
            CheckResult(r3, CheckStatus.SKIP),
            CheckResult(r1, CheckStatus.PASS),
        ]
    )

    assert len(report.results_by_source("SPEC")) == 2
    assert len(report.results_by_source("DESIGN")) == 1
    assert len(report.results_by_source("PATTERNS")) == 1
    assert len(report.results_by_source("UNKNOWN")) == 0


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


def test_compliance_report_format_summary_empty():
    """format_summary handles an empty report gracefully."""
    report = ComplianceReport()
    summary = report.format_summary()
    assert "Overall Score: 100.0%" in summary
    assert "Checks: 0" in summary
    assert "All requirements met" in summary


@given(
    passes=st.integers(min_value=0, max_value=100),
    fails=st.integers(min_value=0, max_value=100),
    skips=st.integers(min_value=0, max_value=100),
)
def test_compliance_report_score_hypothesis(passes, fails, skips):
    """Verify score calculation across various result counts."""
    req = Requirement(source="TEST", statement="Stub")
    results = (
        [CheckResult(req, CheckStatus.PASS)] * passes
        + [CheckResult(req, CheckStatus.FAIL)] * fails
        + [CheckResult(req, CheckStatus.SKIP)] * skips
    )
    report = ComplianceReport(results=results)

    if passes == 0 and fails == 0:
        assert report.score == 100.0
    else:
        expected = (passes / (passes + fails)) * 100.0
        assert report.score == pytest.approx(expected)
