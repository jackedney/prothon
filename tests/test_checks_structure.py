"""Tests for prothon.checks.structure — focused on edge cases and branching logic.

Each check function verifies a structural requirement against a project root.
Tests use tmp_path to build minimal directory layouts.
"""

from __future__ import annotations

from pathlib import Path

from prothon.checks.structure import (
    check_agent_files,
    check_inheritance,
    check_package_structure,
    check_pre_commit,
    check_skills_dir,
)
from prothon.compliance import CheckStatus


# ---------------------------------------------------------------------------
# check_package_structure — conditional branches
# ---------------------------------------------------------------------------


def test_package_structure_multiple_packages_first_has_py_typed(
    tmp_path: Path,
) -> None:
    """PASS when first package has py.typed, even with multiple packages."""
    for name in ("alpha", "beta"):
        pkg = tmp_path / "src" / name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
    (tmp_path / "src" / "alpha" / "py.typed").write_text("")

    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_package_structure_multiple_packages_none_has_py_typed(
    tmp_path: Path,
) -> None:
    """FAIL when multiple packages exist but none has py.typed."""
    for name in ("alpha", "beta"):
        pkg = tmp_path / "src" / name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")

    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "Missing py.typed" in results[0].rationale


def test_package_structure_src_dir_with_only_non_package_dirs(
    tmp_path: Path,
) -> None:
    """FAIL when src/ contains directories without __init__.py."""
    non_pkg = tmp_path / "src" / "data"
    non_pkg.mkdir(parents=True)
    (non_pkg / "readme.txt").write_text("not a package")

    results = check_package_structure(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "No Python packages" in results[0].rationale


# ---------------------------------------------------------------------------
# check_pre_commit — boundary: file vs directory
# ---------------------------------------------------------------------------


def test_pre_commit_directory_not_file(tmp_path: Path) -> None:
    """FAIL when .pre-commit-config.yaml is a directory, not a file."""
    (tmp_path / ".pre-commit-config.yaml").mkdir()
    results = check_pre_commit(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_skills_dir — boundary: file vs directory
# ---------------------------------------------------------------------------


def test_skills_dir_is_file_not_dir(tmp_path: Path) -> None:
    """FAIL when .agents/skills is a file rather than a directory."""
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "skills").write_text("not a directory")

    results = check_skills_dir(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_agent_files — symlink edge cases
# ---------------------------------------------------------------------------


def test_agent_files_partial_symlinks(tmp_path: Path) -> None:
    """Mixed results: AGENTS.md present, one valid symlink, one missing, one regular."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")
    (tmp_path / "CLAUDE.md").symlink_to(agents)
    # GEMINI.md missing entirely
    (tmp_path / "AGENT.md").write_text("regular file, not symlink")

    results = check_agent_files(tmp_path)
    # AGENTS.md -> PASS, CLAUDE.md -> PASS, GEMINI.md -> FAIL, AGENT.md -> FAIL
    assert len(results) == 4
    pass_count = sum(1 for r in results if r.status == CheckStatus.PASS)
    fail_count = sum(1 for r in results if r.status == CheckStatus.FAIL)
    assert pass_count == 2
    assert fail_count == 2


# ---------------------------------------------------------------------------
# check_inheritance — edge cases
# ---------------------------------------------------------------------------


def test_inheritance_only_prothon_error_base(tmp_path: Path) -> None:
    """PASS when the only class is ProthonError itself (no violations)."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text("class ProthonError(Exception): pass\n")
    results = check_inheritance(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_inheritance_multiple_violations_listed(tmp_path: Path) -> None:
    """FAIL rationale lists all violating exception names."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\n"
        "class BadOne(ValueError): pass\n"
        "class BadTwo(RuntimeError): pass\n"
    )
    results = check_inheritance(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert "BadOne" in results[0].rationale
    assert "BadTwo" in results[0].rationale


def test_inheritance_deep_chain_passes(tmp_path: Path) -> None:
    """PASS for a deep chain: ProthonError -> Mid -> Leaf (Mid inherits ProthonError)."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    # Transitive inheritance: LeafError -> MidError -> ProthonError should PASS.
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\n"
        "class MidError(ProthonError): pass\n"
        "class LeafError(MidError): pass\n"
    )
    results = check_inheritance(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_inheritance_non_exception_class_flagged(tmp_path: Path) -> None:
    """Non-Exception base class in exceptions.py is a violation."""
    exc_dir = tmp_path / "src" / "prothon"
    exc_dir.mkdir(parents=True)
    (exc_dir / "exceptions.py").write_text(
        "class ProthonError(Exception): pass\nclass HelperMixin: pass\n"
    )
    results = check_inheritance(tmp_path)
    assert results[0].status == CheckStatus.FAIL
    assert "HelperMixin" in results[0].rationale
