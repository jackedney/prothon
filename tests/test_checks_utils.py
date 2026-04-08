"""Tests for prothon.checks.utils — AST analysis and signature helpers."""

from __future__ import annotations

from pathlib import Path

from prothon.checks.utils import (
    _extract_python_blocks,
    _is_code_dominant,
    _is_signature_only,
    analyze_python_file,
)


def test_analyze_handles_syntax_error(tmp_path: Path) -> None:
    """Files with syntax errors return empty results instead of raising."""
    f = tmp_path / "bad.py"
    f.write_text("def broken(\n")
    assert analyze_python_file(f) == {"imports": set(), "base_classes": {}}


def test_analyze_handles_encoding_error(tmp_path: Path) -> None:
    """Binary files that cause UnicodeDecodeError return empty results."""
    f = tmp_path / "binary.py"
    f.write_bytes(b"\x80\x81\x82\xff\xfe")
    assert analyze_python_file(f) == {"imports": set(), "base_classes": {}}


def test_analyze_from_import_records_module_and_name(tmp_path: Path) -> None:
    """from-import records both the module path and the imported name."""
    f = tmp_path / "mod.py"
    f.write_text("from collections.abc import Mapping, Sequence\n")
    result = analyze_python_file(f)
    assert {"collections.abc", "Mapping", "Sequence"} <= result["imports"]


def test_analyze_class_with_dotted_base(tmp_path: Path) -> None:
    """Class inheriting from a dotted name is captured via ast.unparse."""
    f = tmp_path / "mod.py"
    f.write_text("import ast\nclass V(ast.NodeVisitor): pass\n")
    result = analyze_python_file(f)
    assert "ast.NodeVisitor" in result["base_classes"]["V"]


def test_analyze_multiple_bases(tmp_path: Path) -> None:
    """Class with multiple bases captures all of them."""
    f = tmp_path / "mod.py"
    f.write_text("class C(A, B): pass\n")
    assert analyze_python_file(f)["base_classes"]["C"] == ["A", "B"]


def test_signature_only_accepts_stub_variants() -> None:
    """pass, docstring, and ellipsis bodies are all signature-only."""
    assert _is_signature_only("def a():\n    pass\n") is True
    assert _is_signature_only('def b():\n    """doc"""\n') is True
    assert _is_signature_only("def c():\n    ...\n") is True
    assert _is_signature_only('async def d():\n    """doc"""\n') is True


def test_signature_only_rejects_real_body() -> None:
    """A function with actual logic is NOT signature-only."""
    assert _is_signature_only("def foo():\n    return 42\n") is False


def test_signature_only_class_recursive() -> None:
    """Classes with only stub methods are signature-only; real methods are not."""
    stub_cls = "class P:\n    def m(self) -> None:\n        ...\n"
    real_cls = "class I:\n    def m(self) -> int:\n        return 1\n"
    assert _is_signature_only(stub_cls) is True
    assert _is_signature_only(real_cls) is False


def test_signature_only_rejects_non_definitions() -> None:
    """Top-level assignments and syntax errors are not signatures."""
    assert _is_signature_only("x = 1\n") is False
    assert _is_signature_only("def broken(\n") is False


def test_extract_python_blocks_finds_fenced_blocks() -> None:
    """Extracts python code blocks with correct line numbers."""
    content = "text\n```python\nx = 1\n```\nmore\n```python\ny = 2\n```\n"
    blocks = _extract_python_blocks(content)
    assert len(blocks) == 2
    assert "x = 1" in blocks[0][1]
    assert "y = 2" in blocks[1][1]
    assert blocks[0][0] == 2  # line number of first block


def test_extract_python_blocks_empty_when_no_blocks() -> None:
    """No python blocks means empty list."""
    assert _extract_python_blocks("just plain text") == []


def test_code_dominant_threshold() -> None:
    """Code-dominant when code > 70% of content; not dominant otherwise."""
    big_code = "x" * 80
    assert _is_code_dominant("t" * 10 + big_code, [(1, big_code)]) is True
    small_code = "x" * 10
    assert _is_code_dominant("t" * 100 + small_code, [(1, small_code)]) is False


def test_code_dominant_exact_threshold_is_not_dominant() -> None:
    """Returns False at exactly 70% (strict greater-than)."""
    content = "x" * 100
    code_blocks = [(1, "y" * 70)]
    assert _is_code_dominant(content, code_blocks) is False


def test_analyze_nested_classes(tmp_path: Path) -> None:
    """Inner classes appear in base_classes alongside outer classes."""
    f = tmp_path / "mod.py"
    f.write_text("class Outer:\n    class Inner: pass\n")
    result = analyze_python_file(f)
    assert "Outer" in result["base_classes"]
    assert "Inner" in result["base_classes"]


def test_extract_python_blocks_multiple_line_numbers() -> None:
    """Multiple blocks each get their own start line number."""
    content = (
        "# Header\n\n```python\nblock1\n```\n\n"
        "Text between.\n\n```python\nblock2\n```\n"
    )
    blocks = _extract_python_blocks(content)
    assert len(blocks) == 2
    assert blocks[0][0] == 3
    assert blocks[1][0] == 9
