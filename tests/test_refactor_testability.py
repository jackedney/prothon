"""Tests for refactor/testability: logic detection heuristics."""

from __future__ import annotations


from prothon.refactor.testability import (
    _is_testable_class,
    _is_testable_function,
    _is_trivial_function,
)


def _parse_func(code: str):
    import ast

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return node
    return None


def _parse_class(code: str):
    import ast

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    return None


def test_trivial_pass():
    node = _parse_func("def f(): pass")
    assert node is not None
    assert _is_trivial_function(node)


def test_trivial_return_none():
    node = _parse_func("def f(): return")
    assert node is not None
    assert _is_trivial_function(node)


def test_trivial_return_name():
    node = _parse_func("def f(): return x")
    assert node is not None
    assert _is_trivial_function(node)


def test_nontrivial_branching():
    node = _parse_func("def f(x):\n    if x > 0:\n        return 1\n    return 0")
    assert node is not None
    assert not _is_trivial_function(node)


def test_nontrivial_calculation():
    node = _parse_func("def f(x, y): return x + y")
    assert node is not None
    assert not _is_trivial_function(node)


def test_private_helper_not_testable():
    node = _parse_func("def _helper(x, y): return x + y")
    assert node is not None
    assert not _is_testable_function(node)


def test_public_nontrivial_is_testable():
    node = _parse_func(
        "def process(data):\n    if data:\n        return len(data)\n    return 0"
    )
    assert node is not None
    assert _is_testable_function(node)


def test_testable_class_with_method():
    cls = _parse_class(
        "class Handler:\n    def process(self, x):\n        if x > 0:\n            return x\n        return 0\n"
    )
    assert cls is not None
    assert _is_testable_class(cls)


def test_non_testable_protocol_class():
    cls = _parse_class(
        "from typing import Protocol\nclass Service(Protocol):\n    def run(self) -> int: ...\n"
    )
    assert cls is not None
    assert not _is_testable_class(cls)


def test_non_testable_abc_class():
    cls = _parse_class(
        "from abc import ABC\nclass Base(ABC):\n    def run(self) -> int: ...\n"
    )
    assert cls is not None
    assert not _is_testable_class(cls)


def test_trivial_docstring_plus_return():
    node = _parse_func('def f():\n    """doc."""\n    return x')
    assert node is not None
    assert _is_trivial_function(node)


def test_simple_setter_is_trivial():
    node = _parse_func("def __init__(self, x):\n    self.x = x")
    assert node is not None
    assert _is_trivial_function(node)
