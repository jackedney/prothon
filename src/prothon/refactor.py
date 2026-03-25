from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from prothon.compliance import CheckStatus as ComplianceStatus
from prothon.checks import check_patterns_doc
from prothon.git import rev_parse_head
from prothon.models import Metadata, Promise, Task


@dataclass
class DriftFinding:
    """Represents a single discovery of drift or an optimization opportunity."""

    title: str
    rationale: str
    doc_sections: list[str] = field(default_factory=list)
    files_affected: list[Path] = field(default_factory=list)


def discover_drift(root: Path) -> list[DriftFinding]:
    """Scan the codebase and docs for drift and proactive optimization opportunities.

    Args:
        root: The project root directory.

    Returns:
        A list of DriftFinding objects.
    """
    findings = []
    findings.extend(_check_docs_hierarchy(root))
    findings.extend(_check_patterns_compliance(root))
    findings.extend(_check_large_files(root))
    findings.extend(_check_missing_tests(root))
    return findings


def _check_docs_hierarchy(root: Path) -> list[DriftFinding]:
    """Check for missing core documentation files."""
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
                doc_sections=["PATTERNS.md"],
                files_affected=[patterns_path],
            )
        )
    return findings


def _check_patterns_compliance(root: Path) -> list[DriftFinding]:
    """Check PATTERNS.md for compliance with formatting rules."""
    patterns_path = root / "docs" / "PATTERNS.md"
    if not patterns_path.exists():
        return []

    findings = []
    results = check_patterns_doc(patterns_path)
    for res in results:
        if res.status == ComplianceStatus.FAIL:
            findings.append(
                DriftFinding(
                    title=f"PATTERNS.md drift: {res.requirement.requirement_id or 'Formatting'}",
                    rationale=res.rationale or res.requirement.statement,
                    doc_sections=["PATTERNS.md"],
                    files_affected=[patterns_path],
                )
            )
    return findings


def _check_large_files(root: Path) -> list[DriftFinding]:
    """Identify files that are excessively large and may need refactoring."""
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
                        files_affected=[py_file],
                    )
                )
        except (OSError, UnicodeDecodeError):
            continue
    return findings


def _check_missing_tests(root: Path) -> list[DriftFinding]:
    """Check for source modules with testable logic that lack corresponding tests.

    Only flags modules that contain functions/classes with actual logic (not just
    constants, type definitions, or trivial pass-throughs). Trivial modules don't
    require tests.
    """
    src_dir = root / "src"
    tests_dir = root / "tests"
    if not src_dir.exists():
        return []

    findings = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        # Check if the module has testable logic
        if not _has_testable_logic(py_file):
            continue

        if not _has_matching_test_file(py_file, tests_dir):
            rel = py_file.relative_to(root)
            findings.append(
                DriftFinding(
                    title=f"Missing tests for {py_file.name}",
                    rationale=f"No corresponding test file found for {rel}. "
                    "This module contains functions/classes with logic that should be tested.",
                    files_affected=[tests_dir],
                )
            )
    return findings


def _has_matching_test_file(py_file: Path, tests_dir: Path) -> bool:
    """Check if any test file in tests_dir covers the given module.

    Matches:
    - test_<module>.py anywhere in tests_dir
    - test_*_<module>.py (e.g., test_refactor_impl.py for refactor.py)
    - *_<module>_test.py (e.g., refactor_impl_test.py)
    """
    if not tests_dir.exists():
        return False

    module_stem = py_file.stem
    for test_file in tests_dir.rglob("test_*.py"):
        test_stem = test_file.stem
        # Exact match, suffix match, or tokenized match (handles test_refactor_impl.py for refactor.py)
        if (
            test_stem == f"test_{module_stem}"
            or test_stem.endswith(f"_{module_stem}")
            or module_stem in test_stem.split("_")
        ):
            return True

    for test_file in tests_dir.rglob("*_test.py"):
        test_stem = test_file.stem
        # Exact match, prefix match, or tokenized match
        if (
            test_stem == f"{module_stem}_test"
            or test_stem.startswith(f"{module_stem}_")
            or module_stem in test_stem.split("_")
        ):
            return True

    return False


def _get_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Build a map from child nodes to their parent nodes."""
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _is_method_in_non_testable_class(
    node: ast.FunctionDef | ast.AsyncFunctionDef, parent_map: dict[ast.AST, ast.AST]
) -> bool:
    """Check if a function is a method inside an abstract or Protocol class."""
    parent = parent_map.get(node)
    return isinstance(parent, ast.ClassDef) and not _is_testable_class(parent)


def _has_testable_logic(py_file: Path) -> bool:
    """Check if a Python file contains testable logic.

    Returns False for modules that only contain:
    - Constants and type aliases
    - Data classes with no methods
    - Single-line pass-through functions
    - Abstract base classes / protocols (tested via implementations)
    """
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return False

    parent_map = _get_parent_map(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _is_method_in_non_testable_class(node, parent_map):
                continue
            if _is_testable_function(node):
                return True
        if isinstance(node, ast.ClassDef) and _is_testable_class(node):
            return True
    return False


def _is_testable_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has testable logic."""
    # Skip private helpers (but allow dunder methods)
    if node.name.startswith("_") and not node.name.endswith("_"):
        return False
    # Skip common trivial dunder methods
    if node.name in ("__init__", "__str__", "__repr__", "__len__"):
        if _is_trivial_function(node):
            return False
    return not _is_trivial_function(node)


def _get_base_identifier(base: ast.expr) -> str | None:
    """Extract the simple identifier from a base expression.

    Handles:
    - ast.Name: "ABC" -> "ABC"
    - ast.Attribute: "abc.ABC" -> "ABC"
    - ast.Subscript: "Protocol[T]" -> "Protocol"
    """
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript):
        return _get_base_identifier(base.value)
    return None


def _is_testable_class(node: ast.ClassDef) -> bool:
    """Check if a class has methods with testable logic."""
    for base in node.bases:
        identifier = _get_base_identifier(base)
        if identifier in ("ABC", "Protocol"):
            return False
    return any(
        isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
        and _is_testable_function(item)
        for item in node.body
    )


def _is_trivial_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function body is trivial (just pass, return None, or single expression)."""
    body = node.body

    if len(body) == 1:
        return _is_single_trivial_stmt(body[0])

    if len(body) == 2 and _is_docstring_stmt(body[0]):
        return _is_single_trivial_stmt(body[1])

    return False


def _is_single_trivial_stmt(stmt: ast.stmt) -> bool:
    """Check if a single statement is trivial."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Return):
        return _is_trivial_return(stmt)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return stmt.value.value is ...
    return False


def _is_trivial_return(stmt: ast.Return) -> bool:
    """Check if a return statement is trivial.

    Trivial returns include:
    - return None (or bare return)
    - return some_name
    - return some.attr
    - return delegate.call(...) where args/kwargs are simple names/attributes/constants
    """
    if stmt.value is None:
        return True
    if isinstance(stmt.value, ast.Name | ast.Attribute):
        return True
    if isinstance(stmt.value, ast.Call):
        call = stmt.value
        if not isinstance(call.func, ast.Name | ast.Attribute):
            return False
        return _all_args_simple(call)
    return False


def _all_args_simple(call: ast.Call) -> bool:
    """Check if all arguments in a call are simple (names, attributes, constants)."""
    for arg in call.args:
        if not isinstance(arg, ast.Name | ast.Attribute | ast.Constant):
            return False
    for kw in call.keywords:
        if not isinstance(kw.value, ast.Name | ast.Attribute | ast.Constant):
            return False
    return True


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    """Check if a statement is a docstring."""
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def generate_refactor_promise(root: Path, findings: list[DriftFinding]) -> Promise:
    """Create a phase-scoped promise file containing tasks for the selected findings.

    Args:
        root: The project root directory.
        findings: The selected refactor findings to implement.

    Returns:
        A Promise object populated with tasks.
    """
    try:
        base_commit = rev_parse_head(cwd=root)
    except Exception:
        base_commit = "HEAD"

    metadata = Metadata(
        base_commit=base_commit,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    tasks = []
    for finding in findings:
        files_to_modify = []
        files_to_create = []

        for f in finding.files_affected:
            try:
                rel_path = str(f.relative_to(root))
                if f.exists():
                    files_to_modify.append(rel_path)
                else:
                    files_to_create.append(rel_path)
            except ValueError:
                # Path not relative to root
                continue

        tasks.append(
            Task(
                title=finding.title,
                goal=finding.rationale,
                success_criteria=f"Resolve the drift identified: {finding.title}",
                files_to_modify=files_to_modify,
                files_to_create=files_to_create,
                doc_sections=finding.doc_sections,
            )
        )

    return Promise(metadata=metadata, tasks=tasks)
