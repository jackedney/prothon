from __future__ import annotations

import ast
from pathlib import Path

from prothon.checks import check_patterns_doc
from prothon.compliance import CheckStatus
from prothon.refactor.metrics import (
    collect_cross_module_similarities,
    collect_module_metrics,
)
from prothon.refactor.models import DriftCategory, DriftFinding, Severity
from prothon.refactor.testability import _has_testable_logic, _is_testable_class
from prothon.ui import console

LARGE_FILE_LINE_THRESHOLD = 500
HIGH_INBOUND_THRESHOLD = 10


def discover_drift(root: Path) -> list[DriftFinding]:
    findings = []
    # Wave 0: Doc Quality
    findings.extend(_check_design_quality(root))
    findings.extend(_check_pattern_quality(root))

    # Wave 1: Code Drift
    findings.extend(_check_docs_hierarchy(root))
    findings.extend(_check_patterns_compliance(root))
    findings.extend(_check_large_files(root))
    findings.extend(_check_missing_tests(root))
    return findings


def _check_design_quality(root: Path) -> list[DriftFinding]:
    """Flag high inbound dependency counts (potential subpackages)."""
    findings = []
    try:
        metrics = collect_module_metrics(root)
    except Exception as exc:
        console.print(
            f"Warning: Failed to collect module metrics: {exc}", style="yellow"
        )
        return findings

    for m in metrics:
        if m.imported_by_count > HIGH_INBOUND_THRESHOLD:
            findings.append(
                DriftFinding(
                    title=f"High inbound dependency: {m.path.name}",
                    rationale=f"{m.path.relative_to(root)} is imported by {m.imported_by_count} modules. "
                    "Consider refactoring into a subpackage to improve architectural separation.",
                    category=DriftCategory.DESIGN_QUALITY,
                    severity=Severity.LOW,
                    doc_sections=["DESIGN.md#Architecture"],
                    files_affected=[m.path],
                    evidence=[f"Imported by: {m.imported_by_count} modules"],
                )
            )
    return findings


def _check_pattern_quality(root: Path) -> list[DriftFinding]:
    """Flag duplicate public signatures across modules."""
    findings = []
    try:
        similarities = collect_cross_module_similarities(root)
    except Exception as exc:
        console.print(
            f"Warning: Failed to collect cross-module similarities: {exc}",
            style="yellow",
        )
        return findings

    # Group by function name for concise findings
    grouped: dict[str, list[Path]] = {}
    for s in similarities:
        grouped.setdefault(s.function_name, []).append(s.file_path)

    for func_name, paths in grouped.items():
        rel_paths = [str(p.relative_to(root)) for p in paths]
        findings.append(
            DriftFinding(
                title=f"Duplicate public signature: {func_name}",
                rationale=f"Function '{func_name}' appears with identical name in multiple modules. "
                "Consider defining a shared base class or utility pattern.",
                category=DriftCategory.PATTERN_QUALITY,
                severity=Severity.LOW,
                doc_sections=["PATTERNS.md#Design Patterns"],
                files_affected=paths,
                evidence=[f"Found in: {', '.join(rel_paths)}"],
            )
        )
    return findings


def _check_docs_hierarchy(root: Path) -> list[DriftFinding]:
    findings = []
    docs_dir = root / "docs"
    spec_path = docs_dir / "SPEC.md"
    design_path = docs_dir / "DESIGN.md"
    patterns_path = docs_dir / "PATTERNS.md"

    if not spec_path.is_file():
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

    if spec_path.is_file() and not design_path.is_file():
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

    if design_path.is_file() and not patterns_path.is_file():
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
    try:
        results = check_patterns_doc(patterns_path)
    except Exception as exc:
        console.print(
            f"Warning: PATTERNS.md compliance check failed: {exc}", style="yellow"
        )
        return findings
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
    for py_file in sorted(src_dir.rglob("*.py")):
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
            if len(lines) > LARGE_FILE_LINE_THRESHOLD:
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

    test_stems = _build_test_stem_cache(tests_dir)

    findings = []
    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue

        if not _has_testable_logic(py_file):
            continue

        if not _has_matching_test_file(py_file, test_stems):
            rel = py_file.relative_to(root)
            findings.append(
                DriftFinding(
                    title=f"Missing tests for {py_file.name}",
                    rationale="[HEURISTIC] No corresponding test file found for "
                    f"{rel}. This module contains functions/classes with logic "
                    "that should be tested.",
                    category=DriftCategory.MISSING_TESTS,
                    severity=Severity.LOW,
                    files_affected=[],
                )
            )
    return findings


def _build_test_stem_cache(tests_dir: Path) -> set[str]:
    if not tests_dir.exists():
        return set()

    stems: set[str] = set()
    for test_file in sorted(tests_dir.rglob("*.py")):
        if test_file.name.startswith("test_") or test_file.name.endswith("_test.py"):
            stems.add(test_file.stem)
    return stems


def _has_matching_test_file(py_file: Path, test_stems: set[str]) -> bool:
    module_stem = py_file.stem

    if f"test_{module_stem}" in test_stems:
        return True
    for stem in test_stems:
        if stem == f"{module_stem}_test":
            return True
        if stem.endswith(f"_{module_stem}") or module_stem in stem.split("_"):
            return True
        if stem.startswith(f"{module_stem}_"):
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
