"""Tests for prothon.checks.docs — document validation checks.

Covers check_doc_existence, check_doc_harmonizer, and check_patterns_doc
with focus on requirement IDs, evidence strings, and conditional branches.
"""

from __future__ import annotations

from pathlib import Path

from prothon.checks.docs import (
    check_doc_existence,
    check_doc_harmonizer,
    check_patterns_doc,
)
from prothon.compliance import CheckStatus


# ---------------------------------------------------------------------------
# check_doc_existence
# ---------------------------------------------------------------------------


def test_doc_existence_all_present_evidence_contains_paths(tmp_path: Path) -> None:
    """PASS results include the actual file path as evidence."""
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("SPEC.md", "DESIGN.md", "PATTERNS.md"):
        (docs / name).write_text("# Title")

    results = check_doc_existence(tmp_path)
    assert all(r.status == CheckStatus.PASS for r in results)
    for r in results:
        assert str(tmp_path) in r.evidence


def test_doc_existence_none_present_reports_correct_req_ids(
    tmp_path: Path,
) -> None:
    """FAIL results carry requirement IDs R18 for SPEC and R20 for DESIGN/PATTERNS."""
    results = check_doc_existence(tmp_path)
    # SPEC.md -> R18, DESIGN.md -> R20, PATTERNS.md -> R20
    spec_result = next(r for r in results if "SPEC.md" in r.requirement.statement)
    assert spec_result.requirement.requirement_id == "R18"
    design_result = next(r for r in results if "DESIGN.md" in r.requirement.statement)
    assert design_result.requirement.requirement_id == "R20"


def test_doc_existence_partial_only_spec(tmp_path: Path) -> None:
    """Only SPEC.md present: one PASS (R18), two FAIL (R20)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec")

    results = check_doc_existence(tmp_path)
    passing = [r for r in results if r.status == CheckStatus.PASS]
    failing = [r for r in results if r.status == CheckStatus.FAIL]
    assert len(passing) == 1
    assert passing[0].requirement.requirement_id == "R18"
    assert len(failing) == 2
    assert all(r.requirement.requirement_id == "R20" for r in failing)


def test_doc_existence_fail_rationale_mentions_missing(tmp_path: Path) -> None:
    """FAIL results include a rationale about the document being missing."""
    results = check_doc_existence(tmp_path)
    for r in results:
        assert r.status == CheckStatus.FAIL
        assert "missing" in r.rationale.lower()


# ---------------------------------------------------------------------------
# check_doc_harmonizer
# ---------------------------------------------------------------------------


def test_doc_harmonizer_pass_evidence_is_skill_path(tmp_path: Path) -> None:
    """PASS result evidence points to the SKILL.md file path."""
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-doc-harmonizer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Doc Harmonizer")

    results = check_doc_harmonizer(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS
    assert "SKILL.md" in results[0].evidence


def test_doc_harmonizer_fail_carries_r24(tmp_path: Path) -> None:
    """FAIL result has requirement ID R24 and rationale about missing skill."""
    results = check_doc_harmonizer(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert results[0].requirement.requirement_id == "R24"
    assert "Missing" in results[0].rationale


# ---------------------------------------------------------------------------
# check_patterns_doc
# ---------------------------------------------------------------------------


def test_patterns_doc_missing_returns_two_skips_with_r25_r26(
    tmp_path: Path,
) -> None:
    """Missing PATTERNS.md SKIPs both R25 and R26 with correct rationale."""
    results = check_patterns_doc(tmp_path / "PATTERNS.md")
    assert len(results) == 2
    ids = {r.requirement.requirement_id for r in results}
    assert ids == {"R25", "R26"}
    assert all(r.status == CheckStatus.SKIP for r in results)
    assert all("missing" in r.rationale.lower() for r in results)


def test_patterns_doc_both_r25_and_r26_fail_when_code_dominant_with_impl(
    tmp_path: Path,
) -> None:
    """R25 FAIL (code-dominant) and R26 FAIL (implementation) simultaneously."""
    # Build content that is >70% code with implementation logic
    impl_lines = "\n".join(f"    x = x + {i}" for i in range(50))
    content = (
        "Short.\n"
        "```python\n"
        f"def compute(x: int) -> int:\n{impl_lines}\n    return x\n"
        "```\n"
    )
    p = tmp_path / "PATTERNS.md"
    p.write_text(content)

    results = check_patterns_doc(p)
    r25 = next(r for r in results if r.requirement.requirement_id == "R25")
    r26 = next(r for r in results if r.requirement.requirement_id == "R26")
    assert r25.status == CheckStatus.FAIL
    assert r26.status == CheckStatus.FAIL


def test_patterns_doc_r26_evidence_includes_line_number(tmp_path: Path) -> None:
    """R26 FAIL evidence includes the file path and line number of the offending block."""
    content = (
        "# Patterns\n\n"
        "Lots of natural language rationale to keep things balanced.\n\n"
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
    # Evidence should be "path:line_no"
    assert str(p) in r26.evidence
    assert ":" in r26.evidence


def test_patterns_doc_multiple_blocks_first_bad_fails_r26(tmp_path: Path) -> None:
    """R26 fails on the first non-signature block and stops checking."""
    content = (
        "# Patterns\n\n"
        "A lot of natural language explanation for the patterns used here.\n\n"
        "```python\n"
        "def bad(x: int) -> int:\n"
        "    return x + 1\n"
        "```\n\n"
        "More explanation.\n\n"
        "```python\n"
        "def also_bad(y: int) -> int:\n"
        "    return y * 2\n"
        "```\n"
    )
    p = tmp_path / "PATTERNS.md"
    p.write_text(content)

    results = check_patterns_doc(p)
    r26_results = [r for r in results if r.requirement.requirement_id == "R26"]
    # Only one R26 result due to early break
    assert len(r26_results) == 1
    assert r26_results[0].status == CheckStatus.FAIL
