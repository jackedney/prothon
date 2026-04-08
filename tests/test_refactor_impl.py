from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prothon.refactor import (
    DriftCategory,
    DriftFinding,
    Severity,
    discover_drift,
    generate_refactor_promise,
)
from prothon.refactor.discovery import (
    _check_large_files,
    _check_missing_tests,
    _check_patterns_compliance,
)


def test_discover_drift_missing_docs(tmp_path: Path):
    """Test that discover_drift identifies missing core documentation."""
    # Empty project root
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]

    assert "Missing SPEC.md" in titles
    # DESIGN and PATTERNS depend on SPEC existing in the current implementation
    assert "Missing DESIGN.md" not in titles


def test_discover_drift_docs_hierarchy(tmp_path: Path):
    """Test the sequential discovery of missing docs."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# SPEC")

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing DESIGN.md" in titles
    assert "Missing PATTERNS.md" not in titles

    (docs / "DESIGN.md").write_text("# DESIGN")
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing PATTERNS.md" in titles


def test_discover_drift_large_files(tmp_path: Path):
    """Test identification of files exceeding line limit."""
    src = tmp_path / "src"
    src.mkdir()
    large_file = src / "too_long.py"
    large_file.write_text("\n" * 501)

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Large file: too_long.py" in titles


def test_discover_drift_missing_tests(tmp_path: Path):
    """Test identification of source files with testable logic missing tests."""
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()

    # Module with actual logic (not trivial)
    module = src / "new_feature.py"
    module.write_text("def feat(x):\n    return x * 2\n")

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for new_feature.py" in titles

    # After adding test, it should be gone
    (tests / "test_new_feature.py").write_text("def test_feat(): pass")
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for new_feature.py" not in titles


def test_discover_drift_trivial_module_no_test_needed(tmp_path: Path):
    """Trivial modules (only pass/return None) should not trigger missing test findings."""
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()

    # Module with only trivial functions - no test needed
    module = src / "trivial.py"
    module.write_text(
        "def pass_through(x):\n    return x\n\ndef do_nothing():\n    pass\n"
    )

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for trivial.py" not in titles


def test_simple_setter_not_testable(tmp_path: Path):
    """Classes with only simple setters should not require tests."""
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()

    # Module with only simple setter methods
    module = src / "setters.py"
    module.write_text(
        "class Config:\n"
        "    def __init__(self, enabled: bool):\n"
        "        self.enabled = enabled\n\n"
        "    def set_name(self, name: str):\n"
        "        self.name = name\n"
    )

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for setters.py" not in titles


def test_generate_refactor_promise(tmp_path: Path):
    """Test creating a promise from drift findings."""
    finding = DriftFinding(
        title="Test Finding",
        rationale="Test Rationale",
        doc_sections=["Section"],
        files_affected=[tmp_path / "affected.py"],
    )

    promise = generate_refactor_promise(tmp_path, [finding])

    assert len(promise.tasks) == 1
    task = promise.tasks[0]
    assert task.title == "Test Finding"
    assert task.goal == "Test Rationale"
    assert "affected.py" in task.files_to_create  # Doesn't exist yet


def test_check_patterns_compliance_no_violations(tmp_path: Path):
    """Compliant PATTERNS.md produces no findings."""
    docs = tmp_path / "docs"
    docs.mkdir()
    # Natural-language-dominant doc with a signature-only code block
    (docs / "PATTERNS.md").write_text(
        "# Patterns\n\n"
        "This document describes coding conventions for the project.\n\n"
        "## Naming\n\n"
        "Use descriptive names for all public functions.\n\n"
        "```python\n"
        "def my_function(arg: str) -> None:\n"
        '    """Do something."""\n'
        "```\n\n"
        "## Error Handling\n\n"
        "Always use domain-specific exceptions.\n"
    )

    findings = _check_patterns_compliance(tmp_path)
    assert findings == []


def test_check_patterns_compliance_with_violations(tmp_path: Path):
    """PATTERNS.md with implementation code triggers drift findings."""
    docs = tmp_path / "docs"
    docs.mkdir()
    # Code-dominant doc with implementation logic (violates R25 and R26)
    (docs / "PATTERNS.md").write_text(
        "# P\n```python\nimport os\nx = 1 + 2\ny = x * 3\nz = y + x\na = z * 2\n```\n"
    )

    findings = _check_patterns_compliance(tmp_path)
    assert len(findings) > 0
    titles = [f.title for f in findings]
    # Should reference R25 or R26 in the title
    assert any("PATTERNS.md drift" in t for t in titles)


def test_check_patterns_compliance_missing_file(tmp_path: Path):
    """Missing PATTERNS.md returns no findings."""
    findings = _check_patterns_compliance(tmp_path)
    assert findings == []


def test_check_large_files_boundary_500_lines(tmp_path: Path):
    """A file with exactly 500 lines should NOT be flagged."""
    src = tmp_path / "src"
    src.mkdir()
    boundary_file = src / "boundary.py"
    # 500 lines: "line\n" * 500 gives 500 lines via splitlines()
    boundary_file.write_text("line\n" * 500)

    findings = _check_large_files(tmp_path)
    titles = [f.title for f in findings]
    assert "Large file: boundary.py" not in titles


def test_check_large_files_no_src_dir(tmp_path: Path):
    """No src/ directory returns no findings."""
    findings = _check_large_files(tmp_path)
    assert findings == []


def test_check_missing_tests_skips_init(tmp_path: Path):
    """__init__.py files should be skipped when checking for missing tests."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()

    (src / "__init__.py").write_text("")

    findings = _check_missing_tests(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for __init__.py" not in titles


def test_generate_refactor_promise_git_error_fallback(tmp_path: Path):
    """When rev_parse_head raises, base_commit falls back to 'HEAD'."""
    finding = DriftFinding(
        title="Test",
        rationale="Rationale",
    )

    with patch(
        "prothon.refactor.promise_gen.rev_parse_head",
        side_effect=RuntimeError("no git"),
    ):
        promise = generate_refactor_promise(tmp_path, [finding])

    assert promise.metadata.base_commit == "HEAD"


def test_discover_drift_fully_compliant(tmp_path: Path):
    """A fully compliant project returns no drift findings."""
    # Create all required docs
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec\n\nRequirements go here.\n")
    (docs / "DESIGN.md").write_text("# Design\n\nArchitecture goes here.\n")
    (docs / "PATTERNS.md").write_text(
        "# Patterns\n\n"
        "Natural language describing conventions for the project.\n\n"
        "More text to ensure code is not dominant.\n"
    )

    # Create a small source file with a corresponding test
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "module.py").write_text("def hello(): pass\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_module.py").write_text("def test_hello(): pass\n")

    findings = discover_drift(tmp_path)
    assert findings == []


def test_checkers_set_category_and_severity(tmp_path: Path):
    """Verify that existing drift checkers populate category and severity enums."""
    # Missing docs → doc_hierarchy, high
    findings = discover_drift(tmp_path)
    doc_finding = next(f for f in findings if f.title == "Missing SPEC.md")
    assert doc_finding.category == DriftCategory.DOC_HIERARCHY
    assert doc_finding.severity == Severity.HIGH

    # Large file → large_files, medium
    src = tmp_path / "src"
    src.mkdir()
    (src / "big.py").write_text("x = 1\n" * 501)
    large_findings = _check_large_files(tmp_path)
    assert len(large_findings) == 1
    assert large_findings[0].category == DriftCategory.LARGE_FILES
    assert large_findings[0].severity == Severity.MEDIUM
    assert len(large_findings[0].evidence) == 1


def test_missing_tests_finding_uses_concrete_test_path(tmp_path: Path):
    """Missing tests finding should point at a concrete test file, not the tests dir."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()
    (src / "feature.py").write_text(
        "def logic(x):\n    if x:\n        return 1\n    return 0\n"
    )

    findings = _check_missing_tests(tmp_path)
    assert len(findings) == 1
    affected = findings[0].files_affected
    assert len(affected) == 1
    assert affected[0] == tests / "test_feature.py"
    assert affected[0].name == "test_feature.py"
