from __future__ import annotations

from pathlib import Path

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    ComplianceReport,
    Requirement,
    analyze_python_file,
    check_patterns_doc,
)


def test_analyze_python_file_imports_and_classes(tmp_path: Path):
    """Test AST analysis for imports and class hierarchy."""
    py_path = tmp_path / "test_module.py"
    py_path.write_text("""
import os
from pathlib import Path
from prothon.promise import Task

class MyTask(Task):
    pass

class SimpleClass:
    pass
""")

    analysis = analyze_python_file(py_path)
    assert "os" in analysis["imports"]
    assert "pathlib" in analysis["imports"]
    assert "prothon.promise" in analysis["imports"]

    assert analysis["base_classes"]["MyTask"] == ["Task"]
    assert analysis["base_classes"]["SimpleClass"] == []


def test_check_patterns_doc_compliant(tmp_path: Path):
    """Test check_patterns_doc with a compliant file."""
    patterns_path = tmp_path / "PATTERNS.md"
    patterns_path.write_text("""# Patterns
Rationale for function_one in natural language.
```python
def function_one(arg: int) -> str:
    ...
```
More rationale for class_two.
```python
class ClassTwo:
    def method_one(self):
        pass
```
""")

    results = check_patterns_doc(patterns_path)
    assert all(r.status == CheckStatus.PASS for r in results)


def test_check_patterns_doc_violations(tmp_path: Path):
    """Test check_patterns_doc with R25 and R26 violations."""
    patterns_path = tmp_path / "PATTERNS.md"
    # R26 Violation: Code block contains implementation logic
    patterns_path.write_text("""# Patterns
Rationale.
```python
def function_one(arg: int) -> str:
    return "Implementation logic!"
```
""")

    results = check_patterns_doc(patterns_path)
    r26_result = next(r for r in results if r.requirement.requirement_id == "R26")
    assert r26_result.status == CheckStatus.FAIL
    assert "implementation logic" in r26_result.rationale


def test_compliance_report_scoring():
    """Test the scoring logic in ComplianceReport."""
    req = Requirement("SPEC", "Test Requirement", "R1")
    report = ComplianceReport(
        [
            CheckResult(req, CheckStatus.PASS),
            CheckResult(req, CheckStatus.FAIL),
            CheckResult(req, CheckStatus.SKIP),
        ]
    )

    # Passing checks / relevant (excluding skip) = 1 / 2 = 50%
    assert report.score == 50.0
    assert not report.passed
    assert len(report.failures) == 1


def test_compliance_report_formatting():
    """Test summary formatting for compliance reports."""
    req = Requirement("SPEC", "Test Requirement", "R1")
    report = ComplianceReport(
        [
            CheckResult(req, CheckStatus.PASS),
            CheckResult(req, CheckStatus.FAIL),
        ]
    )

    summary = report.format_summary()
    assert "COMPLIANCE SUMMARY" in summary
    assert "50.0%" in summary
    assert "Found 1 compliance violations" in summary
