"""Tests for ComplianceReport aggregation and CheckResult data model."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    CheckType,
    ComplianceReport,
    Requirement,
)


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


# --- CheckResult serialization tests ---


def test_check_result_to_dict_all_fields():
    """to_dict() returns a dict with all expected fields and correct values."""
    req = Requirement(source="SPEC", statement="Must do X", requirement_id="R5")
    result = CheckResult(
        requirement=req,
        status=CheckStatus.FAIL,
        check_type=CheckType.SEMANTIC,
        evidence="src/foo.py:42",
        rationale="Missing implementation",
    )
    d = result.to_dict()

    assert d["requirement"]["source"] == "SPEC"
    assert d["requirement"]["statement"] == "Must do X"
    assert d["requirement"]["requirement_id"] == "R5"
    assert d["status"] == "FAIL"
    assert d["check_type"] == "SEMANTIC"
    assert d["evidence"] == "src/foo.py:42"
    assert d["rationale"] == "Missing implementation"


def test_check_result_from_dict_reconstructs():
    """from_dict() reconstructs a CheckResult from a dictionary."""
    data = {
        "requirement": {
            "source": "DESIGN",
            "statement": "Use dataclasses",
            "requirement_id": "D3",
        },
        "status": "PASS",
        "check_type": "STATIC",
        "evidence": "src/bar.py:10",
        "rationale": "Found dataclass decorator",
    }
    result = CheckResult.from_dict(data)

    assert result.requirement.source == "DESIGN"
    assert result.requirement.statement == "Use dataclasses"
    assert result.requirement.requirement_id == "D3"
    assert result.status == CheckStatus.PASS
    assert result.check_type == CheckType.STATIC
    assert result.evidence == "src/bar.py:10"
    assert result.rationale == "Found dataclass decorator"


def test_check_result_from_dict_defaults():
    """from_dict() uses defaults for optional fields."""
    data = {
        "requirement": {
            "source": "PATTERNS",
            "statement": "Follow convention",
        },
        "status": "SKIP",
    }
    result = CheckResult.from_dict(data)

    assert result.requirement.requirement_id is None
    assert result.check_type == CheckType.STATIC
    assert result.evidence == ""
    assert result.rationale == ""


def test_check_result_roundtrip():
    """to_dict/from_dict roundtrip preserves all fields."""
    req = Requirement(source="SPEC", statement="Roundtrip test", requirement_id="R99")
    original = CheckResult(
        requirement=req,
        status=CheckStatus.PASS,
        check_type=CheckType.SEMANTIC,
        evidence="tests/test.py:1",
        rationale="All good",
    )
    reconstructed = CheckResult.from_dict(original.to_dict())

    assert reconstructed.requirement.source == original.requirement.source
    assert reconstructed.requirement.statement == original.requirement.statement
    assert (
        reconstructed.requirement.requirement_id == original.requirement.requirement_id
    )
    assert reconstructed.status == original.status
    assert reconstructed.check_type == original.check_type
    assert reconstructed.evidence == original.evidence
    assert reconstructed.rationale == original.rationale


def test_check_result_roundtrip_no_optional_fields():
    """to_dict/from_dict roundtrip works when optional fields are absent/default."""
    req = Requirement(source="DESIGN", statement="Minimal")
    original = CheckResult(requirement=req, status=CheckStatus.SKIP)
    reconstructed = CheckResult.from_dict(original.to_dict())

    assert reconstructed.requirement.source == original.requirement.source
    assert reconstructed.requirement.statement == original.requirement.statement
    assert reconstructed.requirement.requirement_id is None
    assert reconstructed.status == CheckStatus.SKIP
    assert reconstructed.check_type == CheckType.STATIC
    assert reconstructed.evidence == ""
    assert reconstructed.rationale == ""


# --- ComplianceReport merge / add tests ---


def test_compliance_report_merge():
    """merge() combines results from two reports."""
    req1 = Requirement(source="SPEC", statement="R1")
    req2 = Requirement(source="DESIGN", statement="D1")

    report_a = ComplianceReport(results=[CheckResult(req1, CheckStatus.PASS)])
    report_b = ComplianceReport(
        results=[
            CheckResult(req2, CheckStatus.FAIL),
            CheckResult(req2, CheckStatus.SKIP),
        ]
    )

    report_a.merge(report_b)

    assert len(report_a.results) == 3
    assert report_a.results[0].requirement.source == "SPEC"
    assert report_a.results[1].requirement.source == "DESIGN"
    assert report_a.results[2].requirement.source == "DESIGN"
    assert report_a.results[0].status == CheckStatus.PASS
    assert report_a.results[1].status == CheckStatus.FAIL
    assert report_a.results[2].status == CheckStatus.SKIP


def test_compliance_report_merge_empty():
    """merge() with an empty report leaves the original unchanged."""
    req = Requirement(source="SPEC", statement="Existing")
    report = ComplianceReport(results=[CheckResult(req, CheckStatus.PASS)])
    report.merge(ComplianceReport())

    assert len(report.results) == 1


def test_compliance_report_add_from_dicts():
    """add_from_dicts() converts dicts and appends to results."""
    report = ComplianceReport()
    findings = [
        {
            "requirement": {
                "source": "SPEC",
                "statement": "Must exist",
                "requirement_id": "R1",
            },
            "status": "PASS",
            "check_type": "STATIC",
            "evidence": "docs/SPEC.md",
            "rationale": "File found",
        },
        {
            "requirement": {
                "source": "DESIGN",
                "statement": "Use ABC",
            },
            "status": "FAIL",
            "rationale": "Not found",
        },
    ]
    report.add_from_dicts(findings)

    assert len(report.results) == 2
    assert report.results[0].status == CheckStatus.PASS
    assert report.results[0].requirement.requirement_id == "R1"
    assert report.results[0].evidence == "docs/SPEC.md"
    assert report.results[1].status == CheckStatus.FAIL
    assert report.results[1].requirement.source == "DESIGN"
    assert report.results[1].rationale == "Not found"


def test_compliance_report_add_from_dicts_appends():
    """add_from_dicts() appends to existing results, not replaces."""
    req = Requirement(source="SPEC", statement="Pre-existing")
    report = ComplianceReport(results=[CheckResult(req, CheckStatus.PASS)])

    findings = [
        {
            "requirement": {"source": "PATTERNS", "statement": "New finding"},
            "status": "SKIP",
        },
    ]
    report.add_from_dicts(findings)

    assert len(report.results) == 2
    assert report.results[0].requirement.source == "SPEC"
    assert report.results[1].requirement.source == "PATTERNS"
