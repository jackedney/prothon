"""Tests for refactor/models: dataclass construction and enum membership."""

from __future__ import annotations

from pathlib import Path

from prothon.refactor.models import (
    DriftCategory,
    DriftFinding,
    ModuleMetrics,
    PatternOccurrence,
    PatternType,
    Severity,
    SimilarityGroup,
)


def test_drift_category_values():
    assert DriftCategory.DESIGN_QUALITY.value == "design_quality"
    assert DriftCategory.PATTERN_QUALITY.value == "pattern_quality"
    assert DriftCategory.DOC_HIERARCHY.value == "doc_hierarchy"
    assert DriftCategory.PATTERNS_COMPLIANCE.value == "patterns_compliance"
    assert DriftCategory.LARGE_FILES.value == "large_files"
    assert DriftCategory.MISSING_TESTS.value == "missing_tests"


def test_severity_values():
    assert Severity.HIGH.value == "high"
    assert Severity.MEDIUM.value == "medium"
    assert Severity.LOW.value == "low"


def test_pattern_type_values():
    assert PatternType.TRY_EXCEPT_FILE_IO.value == "try_except_file_io"
    assert PatternType.PATH_EXISTS_GUARD.value == "path_exists_guard"


def test_drift_finding_defaults():
    f = DriftFinding(title="test", rationale="reason")
    assert f.category == DriftCategory.DOC_HIERARCHY
    assert f.severity == Severity.MEDIUM
    assert f.doc_sections == []
    assert f.files_affected == []
    assert f.evidence == []


def test_drift_finding_custom():
    f = DriftFinding(
        title="t",
        rationale="r",
        category=DriftCategory.LARGE_FILES,
        severity=Severity.HIGH,
        doc_sections=["DESIGN > Module Structure"],
        files_affected=[Path("src/foo.py")],
        evidence=["423 lines"],
    )
    assert f.category == DriftCategory.LARGE_FILES
    assert f.severity == Severity.HIGH
    assert len(f.evidence) == 1


def test_module_metrics():
    m = ModuleMetrics(
        path=Path("src/mod.py"),
        line_count=100,
        public_function_count=5,
        import_count=3,
        imported_by_count=2,
    )
    assert m.line_count == 100
    assert m.imported_by_count == 2


def test_pattern_occurrence():
    p = PatternOccurrence(
        pattern_type=PatternType.TRY_EXCEPT_FILE_IO,
        file_path=Path("src/mod.py"),
        line_number=42,
    )
    assert p.pattern_type == PatternType.TRY_EXCEPT_FILE_IO


def test_similarity_group():
    s = SimilarityGroup(
        function_name="process",
        file_path=Path("src/a.py"),
        parameters=["path: Path"],
    )
    assert s.function_name == "process"
    assert len(s.parameters) == 1
