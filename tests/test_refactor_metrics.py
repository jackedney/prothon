from __future__ import annotations

from pathlib import Path

from prothon.refactor.metrics import (
    collect_cross_module_similarities,
    collect_module_metrics,
    collect_pattern_usage,
)
from prothon.refactor.models import PatternType


def test_collect_module_metrics_line_function_import_counts(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text(
        "import os\nfrom pathlib import Path\n\ndef hello():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    assert len(metrics) == 1
    m = metrics[0]
    assert m.line_count == 5
    assert m.public_function_count == 1
    assert m.import_count == 2
    assert m.imported_by_count == 0


def test_collect_module_metrics_syntax_error_skipped(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "good.py").write_text("def ok():\n    pass\n")
    (src / "bad.py").write_text("def broken(\n")

    metrics = collect_module_metrics(tmp_path)
    assert len(metrics) == 1
    assert metrics[0].path.name == "good.py"


def test_collect_module_metrics_only_init_files(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")

    assert collect_module_metrics(tmp_path) == []


def test_collect_module_metrics_async_functions_counted(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "amod.py").write_text(
        "async def fetch():\n    pass\n\nasync def process():\n    pass\n"
    )

    metrics = collect_module_metrics(tmp_path)
    assert len(metrics) == 1
    assert metrics[0].public_function_count == 2


def test_collect_pattern_usage_try_except_open_builtin(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "reader.py").write_text(
        "def read_file(path):\n"
        "    try:\n"
        "        f = open(path)\n"
        "        return f.read()\n"
        "    except OSError:\n"
        "        return ''\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert len(occurrences) == 1
    assert occurrences[0].pattern_type == PatternType.TRY_EXCEPT_FILE_IO


def test_collect_pattern_usage_try_except_write_text(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "writer.py").write_text(
        "def safe_write(p, data):\n"
        "    try:\n"
        "        p.write_text(data)\n"
        "    except OSError:\n"
        "        pass\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert len(occurrences) == 1
    assert occurrences[0].pattern_type == PatternType.TRY_EXCEPT_FILE_IO


def test_collect_pattern_usage_path_exists_guard_with_break(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "scanner.py").write_text(
        "from pathlib import Path\n\n"
        "def scan(p):\n"
        "    for item in p.iterdir():\n"
        "        if not item.is_file():\n"
        "            break\n"
        "        print(item)\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    assert any(o.pattern_type == PatternType.PATH_EXISTS_GUARD for o in occurrences)


def test_collect_pattern_usage_both_patterns_in_one_file(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mixed.py").write_text(
        "from pathlib import Path\n\n"
        "def load(p):\n"
        "    if not p.exists():\n"
        "        return None\n"
        "    try:\n"
        "        return p.read_text()\n"
        "    except OSError:\n"
        "        return ''\n"
    )

    occurrences = collect_pattern_usage(tmp_path)
    types = {o.pattern_type for o in occurrences}
    assert PatternType.TRY_EXCEPT_FILE_IO in types
    assert PatternType.PATH_EXISTS_GUARD in types


def test_collect_pattern_usage_syntax_error_skipped(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text("def broken(\n")

    assert collect_pattern_usage(tmp_path) == []


def test_collect_pattern_usage_empty_src(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    assert collect_pattern_usage(tmp_path) == []


def test_collect_cross_module_similarities_parameters_extracted(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def process(data, strict=False):\n    pass\n")
    (src / "b.py").write_text("def process(data, mode='fast'):\n    pass\n")

    groups = collect_cross_module_similarities(tmp_path)
    assert len(groups) == 2
    assert all(g.function_name == "process" for g in groups)
    params_a = next(g.parameters for g in groups if g.file_path.name == "a.py")
    params_b = next(g.parameters for g in groups if g.file_path.name == "b.py")
    assert params_a == ["data", "strict"]
    assert params_b == ["data", "mode"]


def test_collect_cross_module_similarities_syntax_error_skipped(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def process(data):\n    pass\n")
    (src / "b.py").write_text("def broken(\n")

    assert collect_cross_module_similarities(tmp_path) == []


def test_collect_cross_module_similarities_only_init_files(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")

    assert collect_cross_module_similarities(tmp_path) == []


def test_collect_cross_module_similarities_no_src(tmp_path: Path):
    assert collect_cross_module_similarities(tmp_path) == []
