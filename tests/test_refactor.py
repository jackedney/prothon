"""Tests for refactor.py — AST-based testable-logic detection and drift discovery.

Focuses on the complex AST analysis helpers (_has_testable_logic and its
sub-functions) which determine whether a module needs tests, plus edge cases
in discover_drift and generate_refactor_promise not covered by
test_refactor_impl.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prothon.refactor import (
    DriftFinding,
    _has_matching_test_file,
    _has_testable_logic,
    generate_refactor_promise,
)


# ---------------------------------------------------------------------------
# _has_testable_logic — the core AST analysis
# ---------------------------------------------------------------------------


def test_has_testable_logic_with_conditional_branch(tmp_path: Path):
    """A function with if/else branching is testable logic."""
    (tmp_path / "mod.py").write_text(
        "def decide(x):\n    if x > 0:\n        return 'pos'\n    return 'neg'\n"
    )
    assert _has_testable_logic(tmp_path / "mod.py") is True


def test_has_testable_logic_protocol_class_not_testable(tmp_path: Path):
    """Protocol classes should not be flagged as testable."""
    (tmp_path / "proto.py").write_text(
        "from typing import Protocol\n\n"
        "class MyProto(Protocol):\n"
        "    def do_stuff(self, x: int) -> str: ...\n"
    )
    assert _has_testable_logic(tmp_path / "proto.py") is False


def test_has_testable_logic_abc_not_testable(tmp_path: Path):
    """Abstract base classes should not be flagged as testable."""
    (tmp_path / "abc_mod.py").write_text(
        "from abc import ABC\n\n"
        "class Base(ABC):\n"
        "    def template(self):\n"
        "        return self.impl()\n"
    )
    assert _has_testable_logic(tmp_path / "abc_mod.py") is False


def test_has_testable_logic_class_with_real_method(tmp_path: Path):
    """A class with a non-trivial public method is testable."""
    (tmp_path / "real.py").write_text(
        "class Processor:\n"
        "    def run(self, data):\n"
        "        result = []\n"
        "        for item in data:\n"
        "            result.append(item * 2)\n"
        "        return result\n"
    )
    assert _has_testable_logic(tmp_path / "real.py") is True


def test_has_testable_logic_constants_only(tmp_path: Path):
    """A module with only constants and type aliases is not testable."""
    (tmp_path / "consts.py").write_text(
        "MAX_RETRIES = 3\n"
        "DEFAULT_TIMEOUT = 30\n"
        "VALID_STATUSES = frozenset({'ok', 'error'})\n"
    )
    assert _has_testable_logic(tmp_path / "consts.py") is False


def test_has_testable_logic_private_helpers_skipped(tmp_path: Path):
    """Private helpers (single underscore, not dunder) are not testable."""
    (tmp_path / "helpers.py").write_text(
        "def _internal_parse(data):\n"
        "    if data:\n"
        "        return data.split(',')\n"
        "    return []\n"
    )
    assert _has_testable_logic(tmp_path / "helpers.py") is False


def test_has_testable_logic_dunder_nontrivial(tmp_path: Path):
    """A class with a non-trivial __init__ (beyond simple setters) is testable."""
    (tmp_path / "dunder.py").write_text(
        "class Config:\n"
        "    def __init__(self, raw):\n"
        "        if not raw:\n"
        "            raise ValueError('empty')\n"
        "        self.data = raw.split(',')\n"
    )
    assert _has_testable_logic(tmp_path / "dunder.py") is True


def test_has_testable_logic_syntax_error(tmp_path: Path):
    """Files with syntax errors return False (not testable)."""
    (tmp_path / "broken.py").write_text("def foo(\n")
    assert _has_testable_logic(tmp_path / "broken.py") is False


def test_has_testable_logic_pass_through_delegation(tmp_path: Path):
    """A function that just delegates to another call is trivial."""
    (tmp_path / "delegate.py").write_text("def proxy(x):\n    return other_func(x)\n")
    assert _has_testable_logic(tmp_path / "delegate.py") is False


def test_has_testable_logic_async_function(tmp_path: Path):
    """Async functions with real logic are testable."""
    (tmp_path / "async_mod.py").write_text(
        "async def fetch(url):\n"
        "    if not url.startswith('http'):\n"
        "        raise ValueError('bad url')\n"
        "    return url\n"
    )
    assert _has_testable_logic(tmp_path / "async_mod.py") is True


# ---------------------------------------------------------------------------
# _has_matching_test_file — matching heuristics
# ---------------------------------------------------------------------------


def test_matching_test_file_exact(tmp_path: Path):
    """test_<module>.py matches <module>.py."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text("")
    assert _has_matching_test_file(tmp_path / "core.py", tests) is True


def test_matching_test_file_suffix_pattern(tmp_path: Path):
    """test_*_<module>.py matches <module>.py (e.g., test_refactor_impl for refactor)."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_refactor_impl.py").write_text("")
    assert _has_matching_test_file(tmp_path / "refactor.py", tests) is True


def test_matching_test_file_pytest_suffix(tmp_path: Path):
    """*_test.py naming convention matches."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "core_test.py").write_text("")
    assert _has_matching_test_file(tmp_path / "core.py", tests) is True


def test_matching_test_file_no_match(tmp_path: Path):
    """No matching test file returns False."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_unrelated.py").write_text("")
    assert _has_matching_test_file(tmp_path / "core.py", tests) is False


def test_matching_test_file_no_tests_dir(tmp_path: Path):
    """Missing tests directory returns False."""
    assert _has_matching_test_file(tmp_path / "core.py", tmp_path / "tests") is False


# ---------------------------------------------------------------------------
# generate_refactor_promise — edge cases
# ---------------------------------------------------------------------------


def test_generate_promise_existing_vs_new_files(tmp_path: Path):
    """Existing files go to files_to_modify; non-existent go to files_to_create."""
    existing = tmp_path / "exists.py"
    existing.write_text("# exists")
    new_file = tmp_path / "new.py"

    findings = [
        DriftFinding(
            title="Mixed files",
            rationale="Some exist, some don't",
            files_affected=[existing, new_file],
        )
    ]

    with patch("prothon.refactor.rev_parse_head", return_value="abc123"):
        promise = generate_refactor_promise(tmp_path, findings)

    task = promise.tasks[0]
    assert "exists.py" in task.files_to_modify
    assert "new.py" in task.files_to_create


def test_generate_promise_empty_findings(tmp_path: Path):
    """Empty findings list produces a promise with no tasks."""
    with patch("prothon.refactor.rev_parse_head", return_value="abc123"):
        promise = generate_refactor_promise(tmp_path, [])

    assert promise.tasks == []
    assert promise.metadata.base_commit == "abc123"


def test_generate_promise_files_outside_root_skipped(tmp_path: Path):
    """Files not relative to root are silently skipped."""
    outside = Path("/some/other/path/file.py")
    findings = [
        DriftFinding(
            title="Outside root",
            rationale="File outside project",
            files_affected=[outside],
        )
    ]

    with patch("prothon.refactor.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, findings)

    task = promise.tasks[0]
    assert task.files_to_modify == []
    assert task.files_to_create == []


def test_generate_promise_multiple_findings(tmp_path: Path):
    """Multiple findings produce one task each."""
    findings = [
        DriftFinding(title=f"Finding {i}", rationale=f"Reason {i}") for i in range(3)
    ]

    with patch("prothon.refactor.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, findings)

    assert len(promise.tasks) == 3
    assert [t.title for t in promise.tasks] == [
        "Finding 0",
        "Finding 1",
        "Finding 2",
    ]
