"""Tests for prothon.checks.workflows — execute and refactor workflow checks.

Covers edge cases for check_execute_logic and check_refactor_logic:
partial marker presence, require_all semantics, and missing sub-components.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from prothon.checks.workflows import (
    _check_marker,
    check_execute_logic,
    check_refactor_logic,
)
from prothon.compliance import CheckStatus


# ---------------------------------------------------------------------------
# _check_marker — property-based require_all semantics
# ---------------------------------------------------------------------------


@given(
    text=st.text(min_size=0, max_size=200),
    markers=st.lists(
        st.text(min_size=1, max_size=20), min_size=1, max_size=5, unique=True
    ),
    require_all=st.booleans(),
)
@settings(max_examples=100)
def test_check_marker_property(text, markers, require_all):
    """_check_marker satisfies require_all semantics for arbitrary text/markers."""
    present = {m for m in markers if m in text}

    result = _check_marker(
        text,
        markers,
        "R99",
        "test",
        "evidence.txt",
        require_all=require_all,
    )

    if require_all:
        expected_pass = set(markers) <= present
    else:
        expected_pass = bool(present & set(markers))

    if expected_pass:
        assert result.status == CheckStatus.PASS
    else:
        assert result.status == CheckStatus.FAIL
        assert "R99" in result.rationale


# ---------------------------------------------------------------------------
# check_execute_logic — partial marker scenarios
# ---------------------------------------------------------------------------


def test_execute_logic_promise_missing_plan_marker(tmp_path: Path) -> None:
    """R27 FAIL when promise.py exists but lacks 'def plan'."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "promise.py").write_text(
        "expected_lines_added = 0\nfiles_to_modify = []\n"
    )
    results = check_execute_logic(tmp_path)
    r27 = next(r for r in results if r.requirement.requirement_id == "R27")
    assert r27.status == CheckStatus.FAIL
    r28 = next(r for r in results if r.requirement.requirement_id == "R28")
    assert r28.status == CheckStatus.PASS


def test_execute_logic_promise_missing_task_fields(tmp_path: Path) -> None:
    """R28 FAIL when promise.py lacks expected_lines_added (require_all=True)."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "promise.py").write_text("def plan():\n    pass\nfiles_to_modify = []\n")
    results = check_execute_logic(tmp_path)
    r27 = next(r for r in results if r.requirement.requirement_id == "R27")
    assert r27.status == CheckStatus.PASS
    r28 = next(r for r in results if r.requirement.requirement_id == "R28")
    assert r28.status == CheckStatus.FAIL


def test_execute_logic_verify_missing_markers(tmp_path: Path) -> None:
    """R31 FAIL when promise_verify.py exists but lacks required markers."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "promise.py").write_text(
        "def plan():\n    pass\nexpected_lines_added = 0\nfiles_to_modify = []\n"
    )
    (prothon / "promise_verify.py").write_text("def check_task():\n    pass\n")
    results = check_execute_logic(tmp_path)
    r31 = next(r for r in results if r.requirement.requirement_id == "R31")
    assert r31.status == CheckStatus.FAIL


def test_execute_logic_skill_missing_retry_markers(tmp_path: Path) -> None:
    """R33 FAIL when execute skill lacks retry markers."""
    prothon = tmp_path / "src" / "prothon"
    prothon.mkdir(parents=True)
    (prothon / "promise.py").write_text(
        "def plan():\n    pass\nexpected_lines_added = 0\nfiles_to_modify = []\n"
    )
    (prothon / "promise_verify.py").write_text(
        "def check_task():\n    actual_added = 0\n"
    )
    skill_dir = prothon / "skills" / "prothon-execute"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "Fresh instances for fresh-context subagent loops.\nRun pre-commit hooks.\n"
    )
    results = check_execute_logic(tmp_path)
    r33 = next(r for r in results if r.requirement.requirement_id == "R33")
    assert r33.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_refactor_logic — partial skill content
# ---------------------------------------------------------------------------


def test_refactor_logic_skill_missing_wave_pattern(tmp_path: Path) -> None:
    """R39 FAIL when refactor skill lacks the wave pattern marker."""
    refactor_dir = tmp_path / "src" / "prothon" / "refactor"
    refactor_dir.mkdir(parents=True)
    (refactor_dir / "__init__.py").write_text("# refactor\n")

    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-refactor"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Refactor\n"
        "Phase 1: Interactive Discovery\n"
        "Phase 2: Execution with subagent loops\n"
        "reference the specific documentation heading\n"
    )

    results = check_refactor_logic(tmp_path)
    r39 = next(r for r in results if r.requirement.requirement_id == "R39")
    assert r39.status == CheckStatus.FAIL


def test_refactor_logic_skill_missing_discovery_phase(tmp_path: Path) -> None:
    """R40 FAIL when refactor skill lacks discovery phase marker."""
    refactor_dir = tmp_path / "src" / "prothon" / "refactor"
    refactor_dir.mkdir(parents=True)
    (refactor_dir / "__init__.py").write_text("# refactor\n")

    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-refactor"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Refactor\n"
        "DESIGN -> PATTERNS -> CODE\n"
        "Phase 2: Execution with subagent\n"
        "reference the specific documentation heading\n"
    )

    results = check_refactor_logic(tmp_path)
    r40 = next(r for r in results if r.requirement.requirement_id == "R40")
    assert r40.status == CheckStatus.FAIL


def test_refactor_logic_skill_missing_execution_phase(tmp_path: Path) -> None:
    """R41 FAIL when refactor skill lacks 'Phase 2: Execution' (require_all=True)."""
    refactor_dir = tmp_path / "src" / "prothon" / "refactor"
    refactor_dir.mkdir(parents=True)
    (refactor_dir / "__init__.py").write_text("# refactor\n")

    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-refactor"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Refactor\n"
        "DESIGN -> PATTERNS -> CODE\n"
        "Phase 1: Interactive Discovery\n"
        "reference the specific documentation heading\n"
    )

    results = check_refactor_logic(tmp_path)
    r41 = next(r for r in results if r.requirement.requirement_id == "R41")
    assert r41.status == CheckStatus.FAIL


def test_refactor_logic_missing_subpackage_no_skill(tmp_path: Path) -> None:
    """Only R38 FAIL when both refactor subpackage and skill are absent."""
    results = check_refactor_logic(tmp_path)
    assert len(results) == 1
    assert results[0].requirement.requirement_id == "R38"
    assert results[0].status == CheckStatus.FAIL
