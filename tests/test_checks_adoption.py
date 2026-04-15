"""Tests for checks/adoption module: adoption intelligence verification."""

from __future__ import annotations

from pathlib import Path

from prothon.checks.adoption import check_adoption_intelligence
from prothon.compliance import CheckStatus


def test_passes_with_ast_miner_and_adoption(tmp_path: Path):
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    (src / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (src / "adoption.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner\nminer = ASTPatternMiner()\n"
    )
    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_fails_without_ast_miner(tmp_path: Path):
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    results = check_adoption_intelligence(tmp_path)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL


def test_fails_without_import(tmp_path: Path):
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    (src / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (src / "adoption.py").write_text("x = 1\n")
    results = check_adoption_intelligence(tmp_path)
    assert results[0].status == CheckStatus.FAIL
    assert "import" in results[0].rationale.lower()


def test_fails_without_usage(tmp_path: Path):
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    (src / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (src / "adoption.py").write_text("from prothon.ast_miner import ASTPatternMiner\n")
    results = check_adoption_intelligence(tmp_path)
    assert results[0].status == CheckStatus.FAIL
    assert "use" in results[0].rationale.lower()


def test_falls_back_to_scaffold(tmp_path: Path):
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    (src / "ast_miner.py").write_text("class ASTPatternMiner: pass\n")
    (src / "scaffold.py").write_text(
        "from prothon.ast_miner import ASTPatternMiner\nminer = ASTPatternMiner()\n"
    )
    results = check_adoption_intelligence(tmp_path)
    assert results[0].status == CheckStatus.PASS
