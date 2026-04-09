from __future__ import annotations

from pathlib import Path

from prothon.refactor.metrics import (
    collect_cross_module_similarities,
    collect_module_metrics,
    collect_pattern_usage,
)
from prothon.refactor.models import PatternType


def test_collect_module_metrics_counts(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text(
        "import os\nfrom pathlib import Path\n\ndef hello():\n    pass\n"
    )
    m = collect_module_metrics(tmp_path)[0]
    assert m.line_count == 5
    assert m.public_function_count == 1
    assert m.import_count == 2


def test_collect_module_metrics_syntax_error_skipped(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "good.py").write_text("def ok():\n    pass\n")
    (src / "bad.py").write_text("def broken(\n")
    metrics = collect_module_metrics(tmp_path)
    assert len(metrics) == 1
    assert metrics[0].path.name == "good.py"


def test_collect_module_metrics_only_init(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    assert collect_module_metrics(tmp_path) == []


def test_collect_pattern_usage_open_builtin(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "r.py").write_text(
        "def f(p):\n    try:\n        return open(p).read()\n    except OSError:\n        return ''\n"
    )
    occ = collect_pattern_usage(tmp_path)
    assert len(occ) == 1
    assert occ[0].pattern_type == PatternType.TRY_EXCEPT_FILE_IO


def test_collect_pattern_usage_both_patterns(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "m.py").write_text(
        "from pathlib import Path\n"
        "def f(p):\n"
        "    if not p.exists():\n        return None\n"
        "    try:\n        return p.read_text()\n    except OSError:\n        return ''\n"
    )
    types = {o.pattern_type for o in collect_pattern_usage(tmp_path)}
    assert PatternType.TRY_EXCEPT_FILE_IO in types
    assert PatternType.PATH_EXISTS_GUARD in types


def test_collect_pattern_usage_syntax_error(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text("def broken(\n")
    assert collect_pattern_usage(tmp_path) == []


def test_collect_cross_module_similarities_parameters(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def process(data, strict=False):\n    pass\n")
    (src / "b.py").write_text("def process(data, mode='fast'):\n    pass\n")
    groups = collect_cross_module_similarities(tmp_path)
    assert len(groups) == 2
    pa = next(g.parameters for g in groups if g.file_path.name == "a.py")
    pb = next(g.parameters for g in groups if g.file_path.name == "b.py")
    assert pa == ["data", "strict"]
    assert pb == ["data", "mode"]


def test_collect_cross_module_similarities_syntax_error(tmp_path: Path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("def process(data):\n    pass\n")
    (src / "b.py").write_text("def broken(\n")
    assert collect_cross_module_similarities(tmp_path) == []
