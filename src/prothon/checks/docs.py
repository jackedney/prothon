from __future__ import annotations

from pathlib import Path

from prothon.checks.utils import (
    _extract_python_blocks,
    _is_code_dominant,
    _is_signature_only,
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
    results = []
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

    if not patterns_path.exists():
        results.append(
            CheckResult(r25, CheckStatus.SKIP, rationale="PATTERNS.md missing")
        )
        results.append(
            CheckResult(r26, CheckStatus.SKIP, rationale="PATTERNS.md missing")
        )
        return results

    content = patterns_path.read_text()
    code_blocks = _extract_python_blocks(content)

    if not code_blocks:
        results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(patterns_path)))
        results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(patterns_path)))
        return results

    # R25: Heuristic check for rationale (ensure some natural language exists)
    if _is_code_dominant(content, code_blocks):
        results.append(
            CheckResult(
                r25,
                CheckStatus.FAIL,
                evidence=f"{patterns_path}:1",
                rationale="Code blocks dominate PATTERNS.md; rationale should be natural language.",
            )
        )
    else:
        results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(patterns_path)))

    # R26: Signature-only check
    for line_no, block in code_blocks:
        if not _is_signature_only(block):
            results.append(
                CheckResult(
                    r26,
                    CheckStatus.FAIL,
                    evidence=f"{patterns_path}:{line_no}",
                    rationale="Code block contains implementation logic or imports.",
                )
            )
            break
    else:
        results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(patterns_path)))

    return results


def check_doc_existence(root: Path) -> list[CheckResult]:
    """Verify SPEC.md, DESIGN.md, and PATTERNS.md exist."""
    results = []
    doc_reqs = [
        ("SPEC.md", "R18", "SPEC"),
        ("DESIGN.md", "R20", "SPEC"),
        ("PATTERNS.md", "R20", "SPEC"),
    ]
    for doc, req_id, source in doc_reqs:
        req = Requirement(
            source=source,
            requirement_id=req_id,
            statement=f"Prerequisite document {doc} must exist.",
        )
        doc_path = root / "docs" / doc
        if doc_path.is_file():
            results.append(CheckResult(req, CheckStatus.PASS, evidence=str(doc_path)))
        else:
            results.append(
                CheckResult(
                    req,
                    CheckStatus.FAIL,
                    evidence=f"docs/{doc}",
                    rationale="Required document is missing.",
                )
            )
    return results


def _check_refs_directory(
    content: str, refs_dir: Path, results: list[CheckResult]
) -> bool:
    """Verify docs/references/ exists when PATTERNS.md references it.

    Returns True if the directory exists (or wasn't needed), False on failure.
    """
    mentions_refs = "docs/references/" in content
    mentions_pd = "progressive disclosure" in content.lower()

    r44 = Requirement(
        source="SPEC",
        requirement_id="R44",
        statement=(
            "Progressive Disclosure structure: concise SKILL.md with deep "
            "details in a references/ directory."
        ),
    )

    if not (mentions_refs or mentions_pd):
        results.append(
            CheckResult(
                r44,
                CheckStatus.SKIP,
                rationale="No progressive disclosure references in PATTERNS.md",
            )
        )
        return True

    if not refs_dir.is_dir():
        results.append(
            CheckResult(
                r44,
                CheckStatus.FAIL,
                evidence=str(refs_dir),
                rationale=(
                    "PATTERNS.md references docs/references/ but the "
                    "directory does not exist."
                ),
            )
        )
        return False

    results.append(CheckResult(r44, CheckStatus.PASS, evidence=str(refs_dir)))
    return True


def _check_modules_ref(
    content: str, refs_dir: Path, results: list[CheckResult]
) -> None:
    """Verify docs/references/modules.md exists when referenced."""
    if "modules.md" not in content:
        return

    modules_ref = refs_dir / "modules.md"
    if modules_ref.exists():
        return

    req = Requirement(
        source="DESIGN",
        requirement_id="R44",
        statement="Referenced file docs/references/modules.md must exist.",
    )
    results.append(
        CheckResult(
            req,
            CheckStatus.FAIL,
            evidence=str(modules_ref),
            rationale=(
                "PATTERNS.md references docs/references/modules.md "
                "but the file does not exist."
            ),
        )
    )


def _check_refs_r25(refs_dir: Path, results: list[CheckResult]) -> None:
    """Check R25 (natural language rationale) for docs/references/ files."""
    r25 = Requirement(
        source="SPEC",
        requirement_id="R25",
        statement="docs/references/ code blocks must have natural language rationale.",
    )

    for ref_file in sorted(refs_dir.glob("*.md")):
        ref_content = ref_file.read_text()
        code_blocks = _extract_python_blocks(ref_content)
        if not code_blocks:
            continue

        if _is_code_dominant(ref_content, code_blocks):
            results.append(
                CheckResult(
                    r25,
                    CheckStatus.FAIL,
                    evidence=f"{ref_file}:1",
                    rationale=(
                        "Code blocks dominate reference file; rationale "
                        "should be natural language."
                    ),
                )
            )
            return

    results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(refs_dir)))


def _check_refs_r26(refs_dir: Path, results: list[CheckResult]) -> None:
    """Check R26 (signature-only) for docs/references/ files."""
    r26 = Requirement(
        source="SPEC",
        requirement_id="R26",
        statement="docs/references/ code examples must be signatures only.",
    )

    for ref_file in sorted(refs_dir.glob("*.md")):
        ref_content = ref_file.read_text()
        code_blocks = _extract_python_blocks(ref_content)
        for line_no, block in code_blocks:
            if not _is_signature_only(block):
                results.append(
                    CheckResult(
                        r26,
                        CheckStatus.FAIL,
                        evidence=f"{ref_file}:{line_no}",
                        rationale=(
                            "Reference file code block contains "
                            "implementation logic or imports."
                        ),
                    )
                )
                return

    results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(refs_dir)))


def check_progressive_disclosure(root: Path) -> list[CheckResult]:
    """Validate the progressive disclosure documentation structure.

    Checks that docs/references/ exists when PATTERNS.md references it,
    referenced files within it are present, and all code blocks in reference
    files comply with R25-R26 (signature-only).

    Returns:
        List of CheckResult for progressive disclosure requirements.
    """
    results: list[CheckResult] = []
    patterns_path = root / "docs" / "PATTERNS.md"

    if not patterns_path.exists():
        return results

    content = patterns_path.read_text()
    refs_dir = root / "docs" / "references"

    if not _check_refs_directory(content, refs_dir, results):
        return results

    _check_modules_ref(content, refs_dir, results)

    if refs_dir.is_dir():
        _check_refs_r25(refs_dir, results)
        _check_refs_r26(refs_dir, results)

    return results


def check_doc_harmonizer(root: Path) -> list[CheckResult]:
    """Verify Doc-Harmonizer implementation (SPEC R24)."""
    results = []
    req = Requirement(
        source="SPEC",
        requirement_id="R24",
        statement="The doc-harmonizer must detect conflicts between documentation levels and suggest amendments to the lower-authority document, requiring user approval before making changes.",
    )

    skill_path = (
        root / "src" / "prothon" / "skills" / "prothon-doc-harmonizer" / "SKILL.md"
    )
    if skill_path.exists():
        results.append(
            CheckResult(
                requirement=req,
                status=CheckStatus.PASS,
                evidence=str(skill_path),
            )
        )
    else:
        results.append(
            CheckResult(
                requirement=req,
                status=CheckStatus.FAIL,
                evidence=str(skill_path),
                rationale="Missing prothon-doc-harmonizer skill.",
            )
        )
    return results
