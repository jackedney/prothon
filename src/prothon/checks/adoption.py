from __future__ import annotations

from pathlib import Path

from prothon.checks.utils import analyze_python_file
from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


def check_adoption_intelligence(root: Path) -> list[CheckResult]:
    """Verify Adoption Intelligence implementation (SPEC R13)."""
    results = []
    req = Requirement(
        source="SPEC",
        requirement_id="R13",
        statement="Project adoption must use AST analysis to pre-populate PATTERNS.md.",
    )

    miner_path = root / "src" / "prothon" / "ast_miner.py"
    scaffold_path = root / "src" / "prothon" / "scaffold.py"
    adoption_path = root / "src" / "prothon" / "adoption.py"

    if not miner_path.exists():
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence="src/prothon/ast_miner.py",
                rationale="Missing ASTPatternMiner implementation.",
            )
        )
        return results

    # R13 is now implemented in adoption.py after split
    target_path = adoption_path if adoption_path.exists() else scaffold_path

    if not target_path.exists():
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"Missing {target_path.name} to integrate ASTPatternMiner.",
            )
        )
        return results

    analysis = analyze_python_file(target_path)
    imports = analysis.get("imports", set())

    # Check for direct or from-import
    if "prothon.ast_miner" not in imports and "ast_miner" not in imports:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} does not import ASTPatternMiner.",
            )
        )
        return results

    # Check for usage in the file
    content = target_path.read_text()
    if "ASTPatternMiner()" not in content:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} imports but does not appear to use ASTPatternMiner.",
            )
        )
        return results

    results.append(CheckResult(req, CheckStatus.PASS, evidence=str(target_path)))
    return results
