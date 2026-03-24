from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


def analyze_python_file(path: Path) -> dict[str, Any]:
    """Analyze a Python file for imports and base classes using AST.

    Args:
        path: Path to the Python file.

    Returns:
        Dictionary with 'imports' (set) and 'base_classes' (dict).
    """
    if not path.exists():
        return {"imports": set(), "base_classes": {}}

    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return {"imports": set(), "base_classes": {}}

    results: dict[str, Any] = {
        "imports": set(),
        "base_classes": {},
    }

    for node in ast.walk(tree):
        _collect_metadata(node, results)

    return results


def _collect_metadata(node: ast.AST, results: dict[str, Any]) -> None:
    """Helper to collect imports and base classes from an AST node."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            results["imports"].add(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            results["imports"].add(node.module)
    elif isinstance(node, ast.ClassDef):
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
        results["base_classes"][node.name] = bases


def _is_signature_only(code: str) -> bool:
    """Check if Python code contains only signatures."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in tree.body:
        if not _is_signature_node(node):
            return False
    return True


def _is_signature_node(node: ast.AST) -> bool:
    """Verify a node is a signature-only definition."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _is_func_signature(node)
    if isinstance(node, ast.ClassDef):
        for n in node.body:
            if isinstance(n, ast.Pass):
                continue
            if (
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant)
                and (isinstance(n.value.value, str) or n.value.value is Ellipsis)
            ):
                continue
            if not _is_signature_node(n):
                return False
        return True
    return False


def _is_func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Verify function body contains only docstring, pass, or ellipsis."""
    for stmt in node.body:
        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Constant) and (
                isinstance(stmt.value.value, str) or stmt.value.value is Ellipsis
            ):
                continue
        if isinstance(stmt, ast.Pass):
            continue
        return False
    return True


def _is_code_dominant(content: str, code_blocks: list[tuple[int, str]]) -> bool:
    """Heuristic to check if code blocks dominate the document."""
    text_len = len(content)
    code_len = sum(len(block) for _, block in code_blocks)
    return code_len > text_len * 0.7  # 70% threshold


def _extract_python_blocks(content: str) -> list[tuple[int, str]]:
    """Extract python code blocks with start line numbers."""
    blocks = []
    pattern = re.compile(r"```python\s+(.*?)```", re.DOTALL)
    for match in pattern.finditer(content):
        line_no = content.count("\n", 0, match.start()) + 1
        blocks.append((line_no, match.group(1)))
    return blocks
