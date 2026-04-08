from __future__ import annotations

import ast
from pathlib import Path

from prothon.checks import check_patterns_doc
from prothon.compliance import CheckStatus
from prothon.refactor.models import DriftCategory, DriftFinding, Severity
from prothon.refactor.testability import _has_testable_logic, _is_testable_class


def discover_drift(root: Path) -> list[DriftFinding]:
    findings = []
    findings.extend(_check_docs_hierarchy(root))
    findings.extend(_check_patterns_compliance(root))
    findings.extend(_check_large_files(root))
    findings.extend(_check_missing_tests(root))
    return findings


def _check_docs_hierarchy(root: Path) -> list[DriftFinding]:
    findings = []
    docs_dir = root / "docs"
    spec_path = docs_dir / "SPEC.md"
    design_path = docs_dir / "DESIGN.md"
    patterns_path = docs_dir / "PATTERNS.md"

    if not spec_path.exists():
        findings.append(
            DriftFinding(
                title="Missing SPEC.md",
                rationale="SPEC.md is the highest authority in the prothon workflow. "
                "It must exist to define system requirements.",
                category=DriftCategory.DOC_HIERARCHY,
                severity=Severity.HIGH,
                doc_sections=["SPEC.md"],
                files_affected=[spec_path],
            )
        )

    if spec_path.exists() and not design_path.exists():
        findings.append(
            DriftFinding(
                title="Missing DESIGN.md",
                rationale="DESIGN.md defines the architecture and must exist once "
                "requirements are set in SPEC.md.",
                category=DriftCategory.DOC_HIERARCHY,
                severity=Severity.HIGH,
                doc_sections=["DESIGN.md"],
                files_affected=[design_path],
            )
        )

    if design_path.exists() and not patterns_path.exists():
        findings.append(
            DriftFinding(
                title="Missing PATTERNS.md",
                rationale="PATTERNS.md defines code conventions and should exist "
                "once architecture is documented in DESIGN.md.",
                category=DriftCategory.DOC_HIERARCHY,
                severity=Severity.HIGH,
                doc_sections=["PATTERNS.md"],
                files_affected=[patterns_path],
            )
        )
    return findings


def _check_patterns_compliance(root: Path) -> list[DriftFinding]:
    patterns_path = root / "docs" / "PATTERNS.md"
    if not patterns_path.exists():
        return []

    findings = []
    results = check_patterns_doc(patterns_path)
    for res in results:
        if res.status == CheckStatus.FAIL:
            findings.append(
                DriftFinding(
                    title=f"PATTERNS.md drift: {res.requirement.requirement_id or 'Formatting'}",
                    rationale=res.rationale or res.requirement.statement,
                    category=DriftCategory.PATTERNS_COMPLIANCE,
                    severity=Severity.LOW,
                    doc_sections=["PATTERNS.md"],
                    files_affected=[patterns_path],
                )
            )
    return findings


def _check_large_files(root: Path) -> list[DriftFinding]:
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    findings = []
    for py_file in src_dir.rglob("*.py"):
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
            if len(lines) > 500:
                findings.append(
                    DriftFinding(
                        title=f"Large file: {py_file.name}",
                        rationale=f"{py_file.relative_to(root)} has {len(lines)} "
                        "lines. Consider refactoring into smaller modules "
                        "to maintain navigability.",
                        category=DriftCategory.LARGE_FILES,
                        severity=Severity.MEDIUM,
                        files_affected=[py_file],
                        evidence=[f"{py_file.relative_to(root)}: {len(lines)} lines"],
                    )
                )
        except (OSError, UnicodeDecodeError):
            continue
    return findings


def _check_missing_tests(root: Path) -> list[DriftFinding]:
    src_dir = root / "src"
    tests_dir = root / "tests"
    if not src_dir.exists():
        return []

    findings = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        if not _has_testable_logic(py_file):
            continue

        if not _has_matching_test_file(py_file, tests_dir):
            rel = py_file.relative_to(root)
            expected_test = tests_dir / f"test_{py_file.stem}.py"
            findings.append(
                DriftFinding(
                    title=f"Missing tests for {py_file.name}",
                    rationale=f"No corresponding test file found for {rel}. "
                    "This module contains functions/classes with logic that should be tested.",
                    category=DriftCategory.MISSING_TESTS,
                    severity=Severity.MEDIUM,
                    files_affected=[expected_test],
                )
            )
    return findings


def _has_matching_test_file(py_file: Path, tests_dir: Path) -> bool:
    if not tests_dir.exists():
        return False

    module_stem = py_file.stem
    for test_file in tests_dir.rglob("test_*.py"):
        test_stem = test_file.stem
        if (
            test_stem == f"test_{module_stem}"
            or test_stem.endswith(f"_{module_stem}")
            or module_stem in test_stem.split("_")
        ):
            return True

    for test_file in tests_dir.rglob("*_test.py"):
        test_stem = test_file.stem
        if (
            test_stem == f"{module_stem}_test"
            or test_stem.startswith(f"{module_stem}_")
            or module_stem in test_stem.split("_")
        ):
            return True

    return False


def _get_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _is_method_in_non_testable_class(
    node: ast.FunctionDef | ast.AsyncFunctionDef, parent_map: dict[ast.AST, ast.AST]
) -> bool:
    parent = parent_map.get(node)
    return isinstance(parent, ast.ClassDef) and not _is_testable_class(parent)
