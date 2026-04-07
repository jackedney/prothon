from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from prothon.compliance import CheckStatus as ComplianceStatus
from prothon.checks import check_patterns_doc
from prothon.git import rev_parse_head
from prothon.models import Metadata, Promise, Task


class DriftCategory(Enum):
    """Categories of drift detected by the refactor discovery phase."""

    DESIGN_QUALITY = "design_quality"
    PATTERN_QUALITY = "pattern_quality"
    DOC_HIERARCHY = "doc_hierarchy"
    PATTERNS_COMPLIANCE = "patterns_compliance"
    LARGE_FILES = "large_files"
    MISSING_TESTS = "missing_tests"


class Severity(Enum):
    """Impact level of a drift finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PatternType(Enum):
    """Types of recurring structural patterns detected across modules."""

    TRY_EXCEPT_FILE_IO = "try_except_file_io"
    PATH_EXISTS_GUARD = "path_exists_guard"


@dataclass
class DriftFinding:
    """Represents a single discovery of drift or an optimization opportunity."""

    title: str
    rationale: str
    category: DriftCategory = DriftCategory.DOC_HIERARCHY
    severity: Severity = Severity.MEDIUM
    doc_sections: list[str] = field(default_factory=list)
    files_affected: list[Path] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class ModuleMetrics:
    """Metrics for a single Python module used as evidence for Wave 0 analysis."""

    path: Path
    line_count: int
    public_function_count: int
    import_count: int
    imported_by_count: int


@dataclass
class PatternOccurrence:
    """A recurring structural pattern found across modules."""

    pattern_type: PatternType
    file_path: Path
    line_number: int


@dataclass
class SimilarityGroup:
    """A group of public functions with overlapping signatures across modules."""

    function_name: str
    file_path: Path
    parameters: list[str]


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


def collect_module_metrics(root: Path) -> list[ModuleMetrics]:
    """Collect per-module metrics as evidence for Wave 0 doc quality analysis.

    For each Python module under src/, collects line count, public function count,
    import count (outbound), and imported-by count (inbound from other modules
    in the same src/ tree).
    """
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    modules: dict[Path, ModuleMetrics] = {}
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        metrics = _parse_module_metrics(py_file)
        if metrics is not None:
            modules[py_file] = metrics

    _count_inbound_imports(modules, src_dir)
    return list(modules.values())


def _parse_module_metrics(py_file: Path) -> ModuleMetrics | None:
    """Parse a single module and return its metrics, or None on failure."""
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None

    lines = source.splitlines()
    public_funcs = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    )
    import_count = sum(
        1 for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)
    )
    return ModuleMetrics(
        path=py_file,
        line_count=len(lines),
        public_function_count=public_funcs,
        import_count=import_count,
        imported_by_count=0,
    )


def _count_inbound_imports(modules: dict[Path, ModuleMetrics], src_dir: Path) -> None:
    """Increment imported_by_count for each module referenced by other modules.

    Uses fully-qualified module names derived from file paths relative to src_dir
    to avoid stem-collision misattribution. Counts unique importers per target
    (not per import statement).
    """
    fqn_to_path = _build_fqn_map(modules, src_dir)
    for py_file in modules:
        targets = _extract_import_targets(py_file, src_dir, fqn_to_path)
        for target in targets:
            modules[target].imported_by_count += 1


def _build_fqn_map(
    modules: dict[Path, ModuleMetrics], src_dir: Path
) -> dict[str, Path]:
    """Build a mapping from fully-qualified module name to file path."""
    fqn_map: dict[str, Path] = {}
    for py_file in modules:
        rel = py_file.relative_to(src_dir)
        # e.g. prothon/refactor.py -> prothon.refactor
        fqn = str(rel.with_suffix("")).replace("/", ".")
        fqn_map[fqn] = py_file
    return fqn_map


def _extract_import_targets(
    py_file: Path, src_dir: Path, fqn_to_path: dict[str, Path]
) -> set[Path]:
    """Extract unique target module paths imported by py_file."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return set()

    rel = py_file.relative_to(src_dir)
    importer_parts = list(rel.with_suffix("").parts)
    importer_pkg = importer_parts[:-1]  # package path for relative import resolution

    targets: set[Path] = set()
    for node in ast.walk(tree):
        resolved = _resolve_import_fqn(node, importer_pkg)
        if resolved is None:
            continue
        target = fqn_to_path.get(resolved)
        if target and target != py_file:
            targets.add(target)
    return targets


def _resolve_import_fqn(node: ast.AST, importer_pkg: list[str]) -> str | None:
    """Resolve an import node to a fully-qualified module name, or None."""
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    if isinstance(node, ast.ImportFrom):
        return _resolve_import_from(node, importer_pkg)
    return None


def _resolve_import_from(node: ast.ImportFrom, importer_pkg: list[str]) -> str | None:
    """Resolve an ImportFrom node, handling both absolute and relative imports."""
    module = node.module or ""
    if not node.level or node.level == 0:
        return module or None
    # Relative import: level=1 means current package, level=2 means parent, etc.
    base_parts = importer_pkg[: len(importer_pkg) - (node.level - 1)]
    if module:
        return ".".join(base_parts + [module]) if base_parts else module
    return ".".join(base_parts) if base_parts else None


def collect_pattern_usage(root: Path) -> list[PatternOccurrence]:
    """Scan src/ modules for recurring structural patterns.

    Detects: try/except around file I/O, path-existence checks before reads,
    check-then-act conditionals (if not x.exists(): return/raise).
    Returns occurrences grouped by pattern type.
    """
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    occurrences: list[PatternOccurrence] = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        occurrences.extend(_scan_file_patterns(tree, py_file))

    return occurrences


def _scan_file_patterns(tree: ast.AST, py_file: Path) -> list[PatternOccurrence]:
    """Extract pattern occurrences from a single parsed module."""
    results: list[PatternOccurrence] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for body_node in ast.walk(node):
                if isinstance(body_node, ast.Call) and _is_file_io_call(body_node):
                    results.append(
                        PatternOccurrence(
                            pattern_type=PatternType.TRY_EXCEPT_FILE_IO,
                            file_path=py_file,
                            line_number=node.lineno,
                        )
                    )
                    break

        if isinstance(node, ast.If) and _is_path_exists_check(node.test):
            results.append(
                PatternOccurrence(
                    pattern_type=PatternType.PATH_EXISTS_GUARD,
                    file_path=py_file,
                    line_number=node.lineno,
                )
            )
    return results


def _is_file_io_call(node: ast.Call) -> bool:
    """Check if a call node looks like file I/O (read_text, write_text, open)."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in (
            "read_text",
            "write_text",
            "read_bytes",
            "write_bytes",
        )
    if isinstance(node.func, ast.Name):
        return node.func.id == "open"
    return False


def _is_path_exists_check(node: ast.expr) -> bool:
    """Check if an expression is a path.exists() or not path.exists() check."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_path_exists_check(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr in ("exists", "is_file", "is_dir")
    return False


def collect_cross_module_similarities(root: Path) -> list[SimilarityGroup]:
    """Identify public functions across different modules with overlapping signatures.

    Collects all public function signatures (name + parameter names) from src/
    modules and groups functions that share a name across different files.
    """
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    func_map: dict[str, list[SimilarityGroup]] = {}
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        for entry in _extract_public_signatures(py_file):
            func_map.setdefault(entry.function_name, []).append(entry)

    # Only return functions that appear in multiple files
    results: list[SimilarityGroup] = []
    for entries in func_map.values():
        files = {e.file_path for e in entries}
        if len(files) > 1:
            results.extend(entries)
    return results


def _extract_public_signatures(py_file: Path) -> list[SimilarityGroup]:
    """Extract public function signatures from a single module."""
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    entries: list[SimilarityGroup] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            params = [arg.arg for arg in node.args.args if arg.arg != "self"]
            entries.append(
                SimilarityGroup(
                    function_name=node.name,
                    file_path=py_file,
                    parameters=params,
                )
            )
    return entries


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
                    category=DriftCategory.PATTERNS_COMPLIANCE,
                    severity=Severity.LOW,
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
                    category=DriftCategory.MISSING_TESTS,
                    severity=Severity.MEDIUM,
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
    # Simple setter: self.attr = attr (plain or annotated)
    if isinstance(stmt, ast.Assign) and _is_simple_setter(stmt):
        return True
    if isinstance(stmt, ast.AnnAssign) and _is_simple_annotated_setter(stmt):
        return True
    return False


def _is_simple_setter(stmt: ast.Assign) -> bool:
    """Check if assignment is a simple setter like self.enabled = enabled."""
    if len(stmt.targets) != 1:
        return False
    target = stmt.targets[0]
    if not isinstance(target, ast.Attribute):
        return False
    if not isinstance(target.value, ast.Name) or target.value.id != "self":
        return False
    if not isinstance(stmt.value, ast.Name):
        return False
    return target.attr == stmt.value.id


def _is_simple_annotated_setter(stmt: ast.AnnAssign) -> bool:
    """Check if annotated assignment is a simple setter like self.enabled: bool = enabled."""
    if stmt.value is None:
        return False
    target = stmt.target
    if not isinstance(target, ast.Attribute):
        return False
    if not isinstance(target.value, ast.Name) or target.value.id != "self":
        return False
    if not isinstance(stmt.value, ast.Name):
        return False
    return target.attr == stmt.value.id


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
        if isinstance(arg, ast.Starred):
            if not isinstance(arg.value, ast.Name | ast.Attribute | ast.Constant):
                return False
        elif not isinstance(arg, ast.Name | ast.Attribute | ast.Constant):
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
