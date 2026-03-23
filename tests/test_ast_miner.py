from __future__ import annotations

import ast
from pathlib import Path

import pytest

from prothon.ast_miner import ASTPatternMiner, IdiomMatcher


@pytest.fixture
def matcher() -> IdiomMatcher:
    return IdiomMatcher()


@pytest.fixture
def miner() -> ASTPatternMiner:
    return ASTPatternMiner()


def test_idiom_matcher_is_idiom_name(matcher: IdiomMatcher):
    assert matcher.is_idiom_name("Depends")
    assert matcher.is_idiom_name("fastapi.Depends")
    assert matcher.is_idiom_name("typer.Argument")
    assert matcher.is_idiom_name("pydantic.BaseModel")
    assert matcher.is_idiom_name("BaseModel")
    assert not matcher.is_idiom_name("MyClass")
    assert not matcher.is_idiom_name("os.path.join")


def test_idiom_matcher_is_idiom_node(matcher: IdiomMatcher):
    expr = ast.parse("Depends()").body[0]
    assert isinstance(expr, ast.Expr)
    assert matcher.is_idiom_node(expr.value)

    expr = ast.parse("fastapi.Depends()").body[0]
    assert isinstance(expr, ast.Expr)
    assert matcher.is_idiom_node(expr.value)

    expr = ast.parse("123").body[0]
    assert isinstance(expr, ast.Expr)
    assert not matcher.is_idiom_node(expr.value)


def test_idiom_matcher_is_idiom_decorator(matcher: IdiomMatcher):
    # Route decorators
    stmt = ast.parse("@app.get('/')\ndef f(): pass").body[0]
    assert isinstance(stmt, ast.FunctionDef)
    assert matcher.is_idiom_decorator(stmt.decorator_list[0])

    stmt = ast.parse("@router.post('/')\ndef f(): pass").body[0]
    assert isinstance(stmt, ast.FunctionDef)
    assert matcher.is_idiom_decorator(stmt.decorator_list[0])

    # Typer command
    stmt = ast.parse("@app.command()\ndef f(): pass").body[0]
    assert isinstance(stmt, ast.FunctionDef)
    assert matcher.is_idiom_decorator(stmt.decorator_list[0])

    # Standard decorators
    stmt = ast.parse("@classmethod\ndef f(): pass").body[0]
    assert isinstance(stmt, ast.FunctionDef)
    assert matcher.is_idiom_decorator(stmt.decorator_list[0])

    stmt = ast.parse("@staticmethod\ndef f(): pass").body[0]
    assert isinstance(stmt, ast.FunctionDef)
    assert matcher.is_idiom_decorator(stmt.decorator_list[0])

    # Non-idiom
    stmt = ast.parse("@my_decorator\ndef f(): pass").body[0]
    assert isinstance(stmt, ast.FunctionDef)
    assert not matcher.is_idiom_decorator(stmt.decorator_list[0])


def test_extract_basic_functions(miner: ASTPatternMiner, tmp_path: Path):
    code = """
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str = "World"):
    print(f"Hello, {name}")
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    # Expect signatures with Ellipsis bodies
    assert "def add(a: int, b: int) -> int:\n    ..." in result
    assert "def greet(name: str='World'):\n    ..." in result
    assert "return a + b" not in result
    assert "print" not in result


def test_extract_classes(miner: ASTPatternMiner, tmp_path: Path):
    code = """
class Calculator:
    def add(self, a, b):
        return a + b

    @property
    def value(self):
        return 0

class Empty:
    pass
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    assert "class Calculator:" in result
    assert "def add(self, a, b):" in result
    assert "@property" in result
    assert "def value(self):" in result
    assert "class Empty:" in result
    assert "return a + b" not in result
    # Empty classes get a pass in the body
    assert "    pass" in result


def test_extract_async_functions(miner: ASTPatternMiner, tmp_path: Path):
    code = """
async def fetch_data(url: str):
    async with session.get(url) as response:
        return await response.json()
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    assert "async def fetch_data(url: str):" in result
    assert "..." in result
    assert "async with" not in result


def test_extract_fastapi_idioms(miner: ASTPatternMiner, tmp_path: Path):
    code = """
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/")
def read_root(q: str = Depends(get_q)):
    return {"Hello": "World"}
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    # Note: app = FastAPI() is an Assign, so it's NOT extracted by extract_from_file
    # because it only extracts ClassDef and FunctionDef at top-level.

    assert "@app.get('/')" in result
    assert "def read_root(q: str=Depends(get_q)):" in result


def test_extract_pydantic_idioms(miner: ASTPatternMiner, tmp_path: Path):
    code = """
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str = "Anonymous"

    def greet(self):
        return f"Hello {self.name}"
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    assert "class User(BaseModel):" in result
    assert "id: int" in result
    assert "name: str = 'Anonymous'" in result
    assert "def greet(self):" in result


def test_extract_typer_idioms(miner: ASTPatternMiner, tmp_path: Path):
    code = """
import typer

app = typer.Typer()

@app.command()
def main(name: str = typer.Argument(...)):
    print(f"Hello {name}")
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    assert "@app.command()" in result
    assert "def main(name: str=typer.Argument(...)):" in result


def test_scan_directory(miner: ASTPatternMiner, tmp_path: Path):
    (tmp_path / "a.py").write_text("def a(): pass")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "b.py").write_text("def b(): pass")
    (tmp_path / ".hidden.py").write_text("def hidden(): pass")

    result = miner.scan_directory(tmp_path)

    assert "### a.py" in result
    assert "def a():" in result
    assert "### subdir/b.py" in result
    assert "def b():" in result
    assert "hidden" not in result


def test_extract_unsupported_defaults_stripped(miner: ASTPatternMiner, tmp_path: Path):
    code = """
def complex_default(x = some_function_call()):
    pass
"""
    p = tmp_path / "test.py"
    p.write_text(code)

    result = miner.extract_from_file(p)

    assert "def complex_default(x=...):" in result
