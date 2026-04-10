from __future__ import annotations

from pathlib import Path

from prothon.refactor.discovery import (
    _check_design_quality,
    _check_docs_hierarchy,
    _check_large_files,
    _check_missing_tests,
    _check_pattern_quality,
    discover_drift,
)
from prothon.refactor.models import (
    DriftCategory,
    DriftFinding,
    ModuleMetrics,
    Severity,
    SimilarityGroup,
)


def test_check_design_quality_high_inbound(tmp_path: Path, monkeypatch):
    """DESIGN_QUALITY finding when a module has >10 inbound imports."""
    mock_metrics = [
        ModuleMetrics(
            path=tmp_path / "src" / "popular.py",
            line_count=100,
            public_function_count=5,
            import_count=2,
            imported_by_count=11,  # > 10
        )
    ]
    monkeypatch.setattr(
        "prothon.refactor.discovery.collect_module_metrics", lambda _: mock_metrics
    )

    findings = _check_design_quality(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == DriftCategory.DESIGN_QUALITY
    assert "High inbound dependency" in findings[0].title
    assert findings[0].files_affected == [tmp_path / "src" / "popular.py"]


def test_check_pattern_quality_duplicates(tmp_path: Path, monkeypatch):
    """PATTERN_QUALITY finding when identical public signatures exist across modules."""
    mock_sims = [
        SimilarityGroup(
            function_name="common_func",
            file_path=tmp_path / "src" / "a.py",
            parameters=["x"],
        ),
        SimilarityGroup(
            function_name="common_func",
            file_path=tmp_path / "src" / "b.py",
            parameters=["x"],
        ),
    ]
    monkeypatch.setattr(
        "prothon.refactor.discovery.collect_cross_module_similarities",
        lambda _: mock_sims,
    )

    findings = _check_pattern_quality(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == DriftCategory.PATTERN_QUALITY
    assert "Duplicate public signature: common_func" in findings[0].title
    assert len(findings[0].files_affected) == 2


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
