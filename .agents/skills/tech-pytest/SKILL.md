---
name: tech-pytest
description: Reference guide for pytest -- Python testing framework with fixtures and plugins
user-invocable: false
---

# pytest

> Purpose: Testing framework for unit and integration tests (R4: scaffolded toolchain; also used by prothon's own test suite)
> Docs: https://docs.pytest.org/
> Version researched: >=8.0 (latest 8.x)

## Quick Start

```python
# tests/test_scaffold.py
from prothon.scaffold import generate

def test_generate_creates_src_layout(tmp_path):
    generate(tmp_path, data={"module_name": "mylib"})
    assert (tmp_path / "src" / "mylib" / "__init__.py").exists()
```

Run with `pytest tests/` or `poe test`. Tests are discovered automatically by filename (`test_*.py`) and function name (`test_*`).

## Common Patterns

### Fixtures for reusable setup

```python
import pytest
from pathlib import Path

@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a minimal project directory with docs/."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# Spec\n")
    return tmp_path

def test_find_project_root(project_root: Path):
    from prothon.project import find_project_root
    assert find_project_root(project_root) == project_root
```

### Fixture scopes

```python
@pytest.fixture(scope="session")
def expensive_resource():
    """Created once per test session."""
    return build_large_fixture()

@pytest.fixture(scope="module")
def per_module_setup():
    """Created once per test module."""
    ...

@pytest.fixture  # default scope="function"
def per_test_setup():
    """Created fresh for each test function."""
    ...
```

### Parametrize for testing multiple inputs

```python
@pytest.mark.parametrize("exit_code,expected", [
    (0, True),
    (1, False),
    (128, False),
])
def test_check_returncode(exit_code: int, expected: bool):
    assert is_success(exit_code) == expected
```

### Testing exceptions

```python
def test_missing_spec_raises():
    with pytest.raises(FileNotFoundError, match="SPEC.md"):
        load_spec(Path("/nonexistent"))
```

### Temporary directories (built-in)

```python
def test_scaffold(tmp_path: Path):
    """tmp_path provides a unique temp directory per test."""
    result = generate(tmp_path)
    assert (tmp_path / "pyproject.toml").exists()

def test_shared_temp(tmp_path_factory):
    """tmp_path_factory for multiple temp dirs or session-scoped."""
    d1 = tmp_path_factory.mktemp("project1")
    d2 = tmp_path_factory.mktemp("project2")
```

### monkeypatch for patching

```python
def test_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(AssistantNotFoundError):
        check_binary("claude")

def test_env_variable(monkeypatch):
    monkeypatch.setenv("PROTHON_AGENT", "opencode")
    assert resolve_agent() == "opencode"

def test_chdir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert Path.cwd() == tmp_path
```

### Scoped patching with context manager

```python
def test_scoped_patch(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr("os.getcwd", lambda: "/temp")
        import os
        assert os.getcwd() == "/temp"
    # Patch is undone here
```

### conftest.py for shared fixtures

```python
# tests/conftest.py
import pytest

@pytest.fixture
def app_config():
    return {"debug": True, "database_url": "sqlite:///:memory:"}

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
```

Fixtures in `conftest.py` are available to all tests in the same directory and subdirectories without imports.

## Gotchas & Pitfalls

- **`tmp_path` is a `Path` object, not a string.** It is automatically cleaned up after the test session. Do not store references to it beyond the test.
- **Fixture ordering matters.** If fixture A depends on fixture B, declare B as a parameter of A. pytest resolves the dependency graph automatically.
- **`conftest.py` is auto-loaded.** Do not import `conftest.py` directly -- pytest discovers it automatically.
- **`pytest.raises` is a context manager.** The exception must be raised inside the `with` block. Code after the `with` block only runs if the exception was raised and matched.
- **`capfd` vs `capsys`.** Use `capsys` to capture `sys.stdout/stderr` and `capfd` to capture file descriptors (needed when subprocess output goes to fd 1/2 directly).
- **Avoid mutable default fixture values.** Use factory fixtures or `copy.deepcopy` to prevent cross-test contamination.
- **`monkeypatch.setattr` with string targets** (e.g., `"shutil.which"`) patches the attribute at the given dotted path. Use this when the import location matters.

## Idiomatic Usage

**Do:** Use `tmp_path` for all filesystem tests -- never write to the real project directory.

**Do:** Use `conftest.py` for shared fixtures. Prefer small composable fixtures over large monolithic ones.

**Don't:** Use `unittest.TestCase` subclasses -- pure pytest functions with fixtures are simpler and more composable.

**Do:** Use `pytest.mark.parametrize` to test boundary conditions and error cases without duplicating test functions.

**Do:** Name tests descriptively: `test_<function>_<scenario>_<expected>` (e.g., `test_check_task_missing_file_returns_fail`).

**Do:** Use `monkeypatch` for patching environment variables, PATH lookups (`shutil.which`), and module attributes in tests.
