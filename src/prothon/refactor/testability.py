from __future__ import annotations

import ast
from pathlib import Path

from prothon.fs import safe_parse_py


def _has_testable_logic(py_file: Path) -> bool:
    from prothon.refactor.discovery import (
        _get_parent_map,
        _is_method_in_non_testable_class,
    )

    result = safe_parse_py(py_file)
    if result is None:
        return False
    tree, _source = result

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
    if node.name.startswith("_") and not node.name.endswith("_"):
        return False
    if node.name in ("__init__", "__str__", "__repr__", "__len__"):
        if _is_trivial_function(node):
            return False
    return not _is_trivial_function(node)


def _get_base_identifier(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript):
        return _get_base_identifier(base.value)
    return None


def _is_testable_class(node: ast.ClassDef) -> bool:
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
    body = node.body

    if len(body) == 1:
        return _is_single_trivial_stmt(body[0])

    if len(body) == 2 and _is_docstring_stmt(body[0]):
        return _is_single_trivial_stmt(body[1])

    return False


def _is_single_trivial_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Return):
        return _is_trivial_return(stmt)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return stmt.value.value is ...
    if isinstance(stmt, ast.Assign) and _is_simple_setter(stmt):
        return True
    if isinstance(stmt, ast.AnnAssign) and _is_simple_annotated_setter(stmt):
        return True
    return False


def _is_simple_setter(stmt: ast.Assign) -> bool:
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
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )
