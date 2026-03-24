from __future__ import annotations

import ast
from pathlib import Path

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


def _build_alias_map(tree: ast.Module) -> dict[str, str]:
    """Build a mapping from local alias to fully-resolved import name."""
    alias_map: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                alias_map[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                alias_map[alias.asname or alias.name] = full
    return alias_map


def _resolves_to_class(
    node: ast.expr, class_name: str, alias_map: dict[str, str]
) -> bool:
    """Return True if *node* (a Call's func) resolves to *class_name*."""
    if isinstance(node, ast.Name):
        resolved = alias_map.get(node.id, node.id)
        return resolved.split(".")[-1] == class_name
    if isinstance(node, ast.Attribute):
        if node.attr != class_name:
            return False
        # node.attr matches class_name; walk the dotted prefix to the root name,
        # then check if it resolves to the target class via the alias map.
        current: ast.expr = node.value
        while isinstance(current, ast.Attribute):
            current = current.value
        if isinstance(current, ast.Name):
            # If the root name is in alias_map, it was imported — the call
            # resolves to <imported_module>.class_name which is a match.
            return current.id in alias_map
    return False


def _has_class_call(
    tree: ast.Module, class_name: str, alias_map: dict[str, str]
) -> bool:
    """Return True if the AST contains a Call to *class_name*."""
    return any(
        isinstance(node, ast.Call)
        and _resolves_to_class(node.func, class_name, alias_map)
        for node in ast.walk(tree)
    )


def check_adoption_intelligence(root: Path) -> list[CheckResult]:
    """Verify Adoption Intelligence implementation (SPEC R13)."""
    req = Requirement(
        source="SPEC",
        requirement_id="R13",
        statement="Project adoption must use AST analysis to pre-populate PATTERNS.md.",
    )

    miner_path = root / "src" / "prothon" / "ast_miner.py"
    if not miner_path.exists():
        return [
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence="src/prothon/ast_miner.py",
                rationale="Missing ASTPatternMiner implementation.",
            )
        ]

    # R13 is now implemented in adoption.py after split
    adoption_path = root / "src" / "prothon" / "adoption.py"
    scaffold_path = root / "src" / "prothon" / "scaffold.py"
    target_path = adoption_path if adoption_path.exists() else scaffold_path

    if not target_path.exists():
        return [
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"Missing {target_path.name} to integrate ASTPatternMiner.",
            )
        ]

    try:
        tree = ast.parse(target_path.read_text())
    except SyntaxError:
        return [
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} has a syntax error and cannot be parsed.",
            )
        ]

    alias_map = _build_alias_map(tree)

    # Check for import of ast_miner
    if not any("ast_miner" in resolved for resolved in alias_map.values()):
        return [
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} does not import ASTPatternMiner.",
            )
        ]

    # Check for usage
    if not _has_class_call(tree, "ASTPatternMiner", alias_map):
        return [
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} imports but does not appear to use ASTPatternMiner.",
            )
        ]

    return [CheckResult(req, CheckStatus.PASS, evidence=str(target_path))]
