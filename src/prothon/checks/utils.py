from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from prothon.fs import safe_parse_py


def analyze_python_file(path: Path) -> dict[str, Any]:
    """Analyze a Python file for imports and base classes using AST.

    Args:
        path: Path to the Python file.

    Returns:
        Dictionary with 'imports' (set) and 'base_classes' (dict).
    """
    if not path.exists():
        return {"imports": set(), "base_classes": {}}

    tree = safe_parse_py(path)
    if tree is None:
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
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        _collect_imports(node, results["imports"])
    elif isinstance(node, ast.ClassDef):
        results["base_classes"][node.name] = _extract_bases(node)


def _collect_imports(node: ast.Import | ast.ImportFrom, imports: set[str]) -> None:
    """Record module and alias names from an import node."""
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module)
    for alias in node.names:
        imports.add(alias.name)


def _extract_bases(node: ast.ClassDef) -> list[str]:
    """Return the base class names of a class definition."""
    bases: list[str] = []
    for base in node.bases:
        try:
            bases.append(ast.unparse(base))
        except Exception:
            if isinstance(base, ast.Name):
                bases.append(base.id)
    return bases


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


def _is_passthrough_stmt(node: ast.stmt) -> bool:
    """Check if a statement is a pass, docstring, or ellipsis literal."""
    if isinstance(node, ast.Pass):
        return True
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and (isinstance(node.value.value, str) or node.value.value is Ellipsis)
    )


def _is_signature_node(node: ast.AST) -> bool:
    """Verify a node is a signature-only definition."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _is_func_signature(node)
    if isinstance(node, ast.ClassDef):
        return all(_is_passthrough_stmt(n) or _is_signature_node(n) for n in node.body)
    if isinstance(node, ast.AnnAssign):
        return True
    return False


def _is_func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Verify function body contains only docstring, pass, or ellipsis."""
    return all(_is_passthrough_stmt(stmt) for stmt in node.body)


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
