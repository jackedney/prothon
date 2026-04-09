from __future__ import annotations

from pathlib import Path

from prothon.refactor.discovery import (
    _check_docs_hierarchy,
    _check_large_files,
    _check_missing_tests,
    discover_drift,
)
from prothon.refactor.models import DriftCategory, DriftFinding, Severity


def test_discover_drift_returns_drift_finding_list(tmp_path: Path):
    findings = discover_drift(tmp_path)
    assert isinstance(findings, list)
    assert all(isinstance(f, DriftFinding) for f in findings)


def test_discover_drift_empty_project(tmp_path: Path):
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing SPEC.md" in titles


def test_check_docs_hierarchy_missing_spec(tmp_path: Path):
    findings = _check_docs_hierarchy(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "Missing SPEC.md"
    assert f.category == DriftCategory.DOC_HIERARCHY
    assert f.severity == Severity.HIGH
    assert f.doc_sections == ["SPEC.md"]
    assert f.files_affected == [tmp_path / "docs" / "SPEC.md"]


def test_check_docs_hierarchy_missing_design(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec")

    findings = _check_docs_hierarchy(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "Missing DESIGN.md"
    assert f.category == DriftCategory.DOC_HIERARCHY
    assert f.severity == Severity.HIGH
    assert f.doc_sections == ["DESIGN.md"]
    assert f.files_affected == [tmp_path / "docs" / "DESIGN.md"]


def test_check_docs_hierarchy_missing_patterns(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec")
    (docs / "DESIGN.md").write_text("# Design")

    findings = _check_docs_hierarchy(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "Missing PATTERNS.md"
    assert f.category == DriftCategory.DOC_HIERARCHY
    assert f.severity == Severity.HIGH
    assert f.doc_sections == ["PATTERNS.md"]


def test_check_docs_hierarchy_all_present_no_findings(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec")
    (docs / "DESIGN.md").write_text("# Design")
    (docs / "PATTERNS.md").write_text("# Patterns")

    assert _check_docs_hierarchy(tmp_path) == []


def test_check_docs_hierarchy_cascading_check(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec")

    findings = _check_docs_hierarchy(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing SPEC.md" not in titles
    assert "Missing DESIGN.md" in titles
    assert "Missing PATTERNS.md" not in titles


def test_check_large_files_evidence_field(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "big.py").write_text("x = 1\n" * 501)

    findings = _check_large_files(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == DriftCategory.LARGE_FILES
    assert f.severity == Severity.MEDIUM
    assert len(f.evidence) == 1
    assert "501 lines" in f.evidence[0]
    assert "big.py" in f.evidence[0]


def test_check_large_files_no_src(tmp_path: Path):
    assert _check_large_files(tmp_path) == []


def test_check_large_files_no_oversized_files(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "small.py").write_text("x = 1\n")

    assert _check_large_files(tmp_path) == []


def test_check_missing_tests_finding_fields(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()
    (src / "logic.py").write_text(
        "def decide(x):\n    if x:\n        return 1\n    return 0\n"
    )

    findings = _check_missing_tests(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "Missing tests for logic.py"
    assert f.category == DriftCategory.MISSING_TESTS
    assert f.severity == Severity.LOW
    assert f.files_affected == []
    assert "[HEURISTIC]" in f.rationale


def test_check_missing_tests_no_src(tmp_path: Path):
    assert _check_missing_tests(tmp_path) == []


def test_check_missing_tests_with_matching_test(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()
    (src / "logic.py").write_text(
        "def decide(x):\n    if x:\n        return 1\n    return 0\n"
    )
    (tests / "test_logic.py").write_text("def test_decide(): pass")

    assert _check_missing_tests(tmp_path) == []


def test_discover_drift_no_src_no_docs_only_spec_finding(tmp_path: Path):
    findings = discover_drift(tmp_path)
    doc_findings = [f for f in findings if f.category == DriftCategory.DOC_HIERARCHY]
    assert len(doc_findings) == 1
    assert doc_findings[0].title == "Missing SPEC.md"
    large_findings = [f for f in findings if f.category == DriftCategory.LARGE_FILES]
    assert large_findings == []
