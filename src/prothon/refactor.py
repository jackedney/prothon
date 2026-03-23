from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from prothon.compliance import CheckStatus as ComplianceStatus
from prothon.static_checks import check_patterns_doc
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
    """Check for source modules that are missing corresponding test files."""
    src_dir = root / "src"
    tests_dir = root / "tests"
    if not src_dir.exists():
        return []

    findings = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        test_file = tests_dir / f"test_{py_file.stem}.py"
        if not test_file.exists():
            rel = py_file.relative_to(root)
            findings.append(
                DriftFinding(
                    title=f"Missing tests for {py_file.name}",
                    rationale=f"No corresponding test file found for {rel}.",
                    files_affected=[test_file],
                )
            )
    return findings


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
