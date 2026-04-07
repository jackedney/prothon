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
    DriftCategory,
    DriftFinding,
    PatternType,
    Severity,
    _has_matching_test_file,
    _has_testable_logic,
    collect_cross_module_similarities,
    collect_module_metrics,
    collect_pattern_usage,
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


# ---------------------------------------------------------------------------
# DriftFinding — new enum fields
# ---------------------------------------------------------------------------


def test_drift_finding_default_category_and_severity():
    """DriftFinding defaults to DOC_HIERARCHY category and MEDIUM severity."""
    finding = DriftFinding(title="test", rationale="reason")
    assert finding.category == DriftCategory.DOC_HIERARCHY
    assert finding.severity == Severity.MEDIUM
    assert finding.evidence == []


def test_drift_finding_with_explicit_enums():
    """DriftFinding accepts explicit enum values for category and severity."""
    finding = DriftFinding(
        title="test",
        rationale="reason",
        category=DriftCategory.LARGE_FILES,
        severity=Severity.HIGH,
        evidence=["src/big.py: 600 lines"],
    )
    assert finding.category == DriftCategory.LARGE_FILES
    assert finding.severity == Severity.HIGH
    assert finding.evidence == ["src/big.py: 600 lines"]


# ---------------------------------------------------------------------------
# collect_module_metrics
# ---------------------------------------------------------------------------


def test_collect_module_metrics_basic(tmp_path: Path):
    """Collects line count, function count, and import count per module."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text(
        "import os\nimport sys\n\ndef public_func():\n    pass\n\n"
        "def another():\n    pass\n\n"
        "def _private():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    assert len(metrics) == 1
    m = metrics[0]
    assert m.path == src / "core.py"
    assert m.public_function_count == 2  # public_func, another (not _private)
    assert m.import_count == 2  # os, sys


def test_collect_module_metrics_no_src(tmp_path: Path):
    """Returns empty list when src/ doesn't exist."""
    assert collect_module_metrics(tmp_path) == []


def test_collect_module_metrics_imported_by_count(tmp_path: Path):
    """Counts how many other modules import a given module."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "utils.py").write_text("def helper():\n    pass\n")
    (src / "a.py").write_text("from pkg.utils import helper\n\ndef do_a():\n    pass\n")
    (src / "b.py").write_text("from pkg.utils import helper\n\ndef do_b():\n    pass\n")

    metrics = collect_module_metrics(tmp_path)
    utils_metric = next(m for m in metrics if m.path.name == "utils.py")
    assert utils_metric.imported_by_count == 2


def test_collect_module_metrics_no_double_count_same_importer(tmp_path: Path):
    """Multiple imports of the same module from one file count as one importer."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "utils.py").write_text("def helper():\n    pass\n\ndef other():\n    pass\n")
    (src / "a.py").write_text(
        "from pkg.utils import helper\nfrom pkg.utils import other\n\n"
        "def do_a():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    utils_metric = next(m for m in metrics if m.path.name == "utils.py")
    assert utils_metric.imported_by_count == 1  # a.py counts once, not twice


def test_collect_module_metrics_no_stem_collision(tmp_path: Path):
    """Modules with the same stem in different packages are distinguished."""
    src = tmp_path / "src"
    pkg_a = src / "pkg_a"
    pkg_b = src / "pkg_b"
    pkg_a.mkdir(parents=True)
    pkg_b.mkdir(parents=True)
    (pkg_a / "__init__.py").write_text("")
    (pkg_b / "__init__.py").write_text("")
    (pkg_a / "utils.py").write_text("def a_helper():\n    pass\n")
    (pkg_b / "utils.py").write_text("def b_helper():\n    pass\n")
    # pkg_b/consumer.py imports pkg_a.utils — only pkg_a/utils should get the count
    (pkg_b / "consumer.py").write_text(
        "from pkg_a.utils import a_helper\n\ndef do_b():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    a_utils = next(m for m in metrics if m.path == pkg_a / "utils.py")
    b_utils = next(m for m in metrics if m.path == pkg_b / "utils.py")
    assert a_utils.imported_by_count == 1
    assert b_utils.imported_by_count == 0


def test_collect_module_metrics_relative_import(tmp_path: Path):
    """Relative imports are resolved correctly."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "utils.py").write_text("def helper():\n    pass\n")
    (src / "core.py").write_text(
        "from .utils import helper\n\ndef do_core():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    utils_metric = next(m for m in metrics if m.path.name == "utils.py")
    assert utils_metric.imported_by_count == 1


def test_collect_module_metrics_absolute_import(tmp_path: Path):
    """ast.Import (import pkg.utils) is handled."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "utils.py").write_text("def helper():\n    pass\n")
    (src / "core.py").write_text("import pkg.utils\n\ndef do_core():\n    pass\n")

    metrics = collect_module_metrics(tmp_path)
    utils_metric = next(m for m in metrics if m.path.name == "utils.py")
    assert utils_metric.imported_by_count == 1


def test_collect_module_metrics_multi_alias_import(tmp_path: Path):
    """'import pkg.a, pkg.b' resolves both targets."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def func_a():\n    pass\n")
    (src / "b.py").write_text("def func_b():\n    pass\n")
    (src / "core.py").write_text("import pkg.a, pkg.b\n\ndef do_core():\n    pass\n")

    metrics = collect_module_metrics(tmp_path)
    a_metric = next(m for m in metrics if m.path.name == "a.py")
    b_metric = next(m for m in metrics if m.path.name == "b.py")
    assert a_metric.imported_by_count == 1
    assert b_metric.imported_by_count == 1


def test_collect_module_metrics_from_pkg_import_mod(tmp_path: Path):
    """'from pkg import mod' resolves to pkg.mod when mod is a module."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "utils.py").write_text("def helper():\n    pass\n")
    (src / "core.py").write_text("from pkg import utils\n\ndef do_core():\n    pass\n")

    metrics = collect_module_metrics(tmp_path)
    utils_metric = next(m for m in metrics if m.path.name == "utils.py")
    assert utils_metric.imported_by_count == 1


# ---------------------------------------------------------------------------
# collect_pattern_usage
# ---------------------------------------------------------------------------


def test_collect_pattern_usage_try_except_file_io(tmp_path: Path):
    """Detects try/except around file I/O calls."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "reader.py").write_text(
        "from pathlib import Path\n\n"
        "def read_config(p: Path):\n"
        "    try:\n"
        "        return p.read_text()\n"
        "    except OSError:\n"
        "        return ''\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert len(occurrences) == 1
    assert occurrences[0].pattern_type == PatternType.TRY_EXCEPT_FILE_IO
    assert occurrences[0].file_path == src / "reader.py"


def test_collect_pattern_usage_path_exists_guard(tmp_path: Path):
    """Detects path.exists() guard patterns."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "loader.py").write_text(
        "from pathlib import Path\n\n"
        "def load(p: Path):\n"
        "    if not p.exists():\n"
        "        return None\n"
        "    return p.read_text()\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert any(o.pattern_type == PatternType.PATH_EXISTS_GUARD for o in occurrences)


def test_collect_pattern_usage_exists_check_without_guard_not_detected(tmp_path: Path):
    """path.exists() checks without a guard action (return/raise) are not flagged."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "checker.py").write_text(
        "from pathlib import Path\n\n"
        "def check(p: Path):\n"
        "    if p.exists():\n"
        "        print('found')\n"
        "    return True\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert not any(o.pattern_type == PatternType.PATH_EXISTS_GUARD for o in occurrences)


def test_collect_pattern_usage_no_src(tmp_path: Path):
    """Returns empty list when src/ doesn't exist."""
    assert collect_pattern_usage(tmp_path) == []


# ---------------------------------------------------------------------------
# collect_cross_module_similarities
# ---------------------------------------------------------------------------


def test_collect_cross_module_similarities_shared_name(tmp_path: Path):
    """Identifies public functions with the same name across different modules."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def validate(data, strict=False):\n    pass\n")
    (src / "b.py").write_text("def validate(data, mode='fast'):\n    pass\n")

    groups = collect_cross_module_similarities(tmp_path)
    assert len(groups) == 2  # One entry per function, both named "validate"
    names = {g.function_name for g in groups}
    assert names == {"validate"}
    files = {g.file_path for g in groups}
    assert files == {src / "a.py", src / "b.py"}


def test_collect_cross_module_similarities_private_excluded(tmp_path: Path):
    """Private functions are excluded from similarity analysis."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def _helper(x):\n    pass\n")
    (src / "b.py").write_text("def _helper(x):\n    pass\n")

    groups = collect_cross_module_similarities(tmp_path)
    assert groups == []


def test_collect_cross_module_similarities_unique_names(tmp_path: Path):
    """Functions with unique names across modules are not returned."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def func_a():\n    pass\n")
    (src / "b.py").write_text("def func_b():\n    pass\n")

    groups = collect_cross_module_similarities(tmp_path)
    assert groups == []


def test_collect_cross_module_similarities_no_src(tmp_path: Path):
    """Returns empty list when src/ doesn't exist."""
    assert collect_cross_module_similarities(tmp_path) == []


def test_collect_pattern_usage_is_file_guard(tmp_path: Path):
    """Detects path.is_file() guard patterns with return."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "checker.py").write_text(
        "from pathlib import Path\n\n"
        "def load(p: Path):\n"
        "    if not p.is_file():\n"
        "        raise FileNotFoundError\n"
        "    return p.read_text()\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert any(o.pattern_type == PatternType.PATH_EXISTS_GUARD for o in occurrences)


def test_collect_pattern_usage_is_dir_guard(tmp_path: Path):
    """Detects path.is_dir() guard patterns with return."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "checker.py").write_text(
        "from pathlib import Path\n\n"
        "def scan(p: Path):\n"
        "    if not p.is_dir():\n"
        "        return []\n"
        "    return list(p.iterdir())\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert any(o.pattern_type == PatternType.PATH_EXISTS_GUARD for o in occurrences)


def test_collect_pattern_usage_try_except_io_in_handler(tmp_path: Path):
    """Detects try/except file I/O even when I/O call is in the except handler."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "recovery.py").write_text(
        "from pathlib import Path\n\n"
        "def safe_read(p: Path):\n"
        "    try:\n"
        "        return p.read_text()\n"
        "    except OSError:\n"
        "        return ''\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert len(occurrences) == 1
    assert occurrences[0].pattern_type == PatternType.TRY_EXCEPT_FILE_IO


def test_collect_module_metrics_imported_by_zero_when_not_imported(tmp_path: Path):
    """Modules not imported by anyone have imported_by_count == 0."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "isolated.py").write_text("def standalone():\n    pass\n")
    (src / "other.py").write_text("def other_func():\n    pass\n")

    metrics = collect_module_metrics(tmp_path)
    for m in metrics:
        assert m.imported_by_count == 0


def test_collect_module_metrics_relative_import_level_two(tmp_path: Path):
    """Relative imports with level > 1 (from ..pkg) resolve correctly."""
    src = tmp_path / "src"
    pkg = src / "pkg"
    sub = pkg / "sub"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (sub / "__init__.py").write_text("")
    (pkg / "utils.py").write_text("def helper():\n    pass\n")
    (sub / "core.py").write_text(
        "from ..utils import helper\n\ndef do_core():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    utils_metric = next(m for m in metrics if m.path.name == "utils.py")
    assert utils_metric.imported_by_count == 1
