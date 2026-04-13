from __future__ import annotations

from pathlib import Path

from prothon.checks.utils import (
    _extract_python_blocks,
    _is_code_dominant,
    _is_signature_only,
    check_path_exists,
)
from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


def check_patterns_doc(patterns_path: Path) -> list[CheckResult]:
    """Verify PATTERNS.md code blocks follow R25-R26 rules.

    Args:
        patterns_path: Path to PATTERNS.md.

    Returns:
        List of CheckResult for R25 and R26.
    """
    results: list[CheckResult] = []
    if not patterns_path.exists():
        r25 = Requirement(
            source="SPEC",
            requirement_id="R25",
            statement="PATTERNS.md rationale expressed in natural language, not code.",
        )
        r26 = Requirement(
            source="SPEC",
            requirement_id="R26",
            statement="PATTERNS.md code examples limited to signatures only.",
        )
        results.append(
            CheckResult(r25, CheckStatus.SKIP, rationale="PATTERNS.md missing")
        )
        results.append(
            CheckResult(r26, CheckStatus.SKIP, rationale="PATTERNS.md missing")
        )
        return results
    _check_r25_r26(patterns_path, results)
    return results


def check_doc_existence(root: Path) -> list[CheckResult]:
    """Verify SPEC.md, DESIGN.md, and PATTERNS.md exist."""
    results = []
    doc_reqs = [
        ("docs/SPEC.md", "R18", "SPEC"),
        ("docs/DESIGN.md", "R20", "SPEC"),
        ("docs/PATTERNS.md", "R20", "SPEC"),
    ]
    for rel_path, req_id, source in doc_reqs:
        req = Requirement(
            source=source,
            requirement_id=req_id,
            statement=f"Prerequisite document {rel_path.split('/')[-1]} must exist.",
        )
        results.append(
            check_path_exists(
                root,
                rel_path,
                req,
                fail_rationale="Required document is missing.",
            )
        )
    return results


def _check_r25_r26(target: Path, results: list[CheckResult]) -> None:
    if not target.exists():
        return
    content = target.read_text()
    code_blocks = _extract_python_blocks(content)
    r25 = Requirement(
        source="SPEC",
        requirement_id="R25",
        statement=f"{target.name} rationale expressed in natural language, not code.",
    )
    r26 = Requirement(
        source="SPEC",
        requirement_id="R26",
        statement=f"{target.name} code examples limited to signatures only.",
    )
    if not code_blocks:
        results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(target)))
        results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(target)))
        return
    if _is_code_dominant(content, code_blocks):
        results.append(
            CheckResult(
                r25,
                CheckStatus.FAIL,
                evidence=f"{target}:1",
                rationale=f"Code blocks dominate {target.name}.",
            )
        )
    else:
        results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(target)))
    for line_no, block in code_blocks:
        if not _is_signature_only(block):
            results.append(
                CheckResult(
                    r26,
                    CheckStatus.FAIL,
                    evidence=f"{target}:{line_no}",
                    rationale="Code block contains implementation logic.",
                )
            )
            return
    results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(target)))


def check_progressive_disclosure(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    patterns_path = root / "docs" / "PATTERNS.md"
    if not patterns_path.exists():
        return results
    content = patterns_path.read_text()
    refs_dir = root / "docs" / "references"
    mentions = (
        "docs/references/" in content or "progressive disclosure" in content.lower()
    )
    r44 = Requirement(
        source="SPEC",
        requirement_id="R44",
        statement="Progressive Disclosure structure with a references/ directory.",
    )
    if not mentions:
        results.append(
            CheckResult(
                r44,
                CheckStatus.SKIP,
                rationale="No progressive disclosure references in PATTERNS.md",
            )
        )
        return results
    if not refs_dir.is_dir():
        results.append(
            CheckResult(
                r44,
                CheckStatus.FAIL,
                evidence=str(refs_dir),
                rationale="PATTERNS.md references docs/references/ but directory missing.",
            )
        )
        return results
    results.append(CheckResult(r44, CheckStatus.PASS, evidence=str(refs_dir)))
    if "modules.md" in content and not (refs_dir / "modules.md").exists():
        results.append(
            CheckResult(
                Requirement(
                    source="DESIGN",
                    requirement_id="R44",
                    statement="Referenced file docs/references/modules.md must exist.",
                ),
                CheckStatus.FAIL,
                evidence=str(refs_dir / "modules.md"),
                rationale="Referenced modules.md missing.",
            )
        )
    for ref_file in sorted(refs_dir.glob("*.md")):
        _check_r25_r26(ref_file, results)
    return results


def check_doc_harmonizer(root: Path) -> list[CheckResult]:
    """Verify Doc-Harmonizer implementation (SPEC R24)."""
    req = Requirement(
        source="SPEC",
        requirement_id="R24",
        statement="The doc-harmonizer must detect conflicts between documentation levels and suggest amendments to the lower-authority document, requiring user approval before making changes.",
    )
    return [
        check_path_exists(
            root,
            "src/prothon/skills/prothon-doc-harmonizer/SKILL.md",
            req,
            fail_rationale="Missing prothon-doc-harmonizer skill.",
        )
    ]
