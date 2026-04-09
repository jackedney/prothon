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


def test_check_docs_hierarchy_missing_spec_fields(tmp_path: Path):
    findings = _check_docs_hierarchy(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.title == "Missing SPEC.md"
    assert f.category == DriftCategory.DOC_HIERARCHY
    assert f.severity == Severity.HIGH
    assert f.doc_sections == ["SPEC.md"]
    assert f.files_affected == [tmp_path / "docs" / "SPEC.md"]


def test_check_docs_hierarchy_cascading(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# S")
    findings = _check_docs_hierarchy(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing SPEC.md" not in titles
    assert "Missing DESIGN.md" in titles
    assert "Missing PATTERNS.md" not in titles

    (docs / "DESIGN.md").write_text("# D")
    findings = _check_docs_hierarchy(tmp_path)
    assert findings[0].title == "Missing PATTERNS.md"


def test_check_docs_hierarchy_all_present(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# S")
    (docs / "DESIGN.md").write_text("# D")
    (docs / "PATTERNS.md").write_text("# P")
    assert _check_docs_hierarchy(tmp_path) == []


def test_check_large_files_evidence_and_severity(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "big.py").write_text("x = 1\n" * 501)
    findings = _check_large_files(tmp_path)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == DriftCategory.LARGE_FILES
    assert f.severity == Severity.MEDIUM
    assert "501 lines" in f.evidence[0]


def test_check_large_files_no_oversized(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "small.py").write_text("x = 1\n")
    assert _check_large_files(tmp_path) == []


def test_check_missing_tests_no_src(tmp_path: Path):
    assert _check_missing_tests(tmp_path) == []


def test_discover_drift_fully_compliant(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# S\nRequirements.\n")
    (docs / "DESIGN.md").write_text("# D\nArchitecture.\n")
    (docs / "PATTERNS.md").write_text("# P\nConventions described here.\n")
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "m.py").write_text("def f(): pass\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_m.py").write_text("def test_f(): pass\n")
    assert discover_drift(tmp_path) == []
