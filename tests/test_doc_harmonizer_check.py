from pathlib import Path

from prothon.compliance import CheckStatus
from prothon.checks import check_doc_harmonizer


def test_check_doc_harmonizer_pass(tmp_path: Path) -> None:
    skill_dir = tmp_path / "src" / "prothon" / "skills" / "prothon-doc-harmonizer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Doc-Harmonizer Skill")

    results = check_doc_harmonizer(tmp_path)

    assert len(results) == 1
    assert results[0].requirement.requirement_id == "R24"
    assert results[0].status == CheckStatus.PASS
    assert "prothon-doc-harmonizer" in results[0].evidence


def test_check_doc_harmonizer_fail(tmp_path: Path) -> None:
    # No skill file created
    results = check_doc_harmonizer(tmp_path)

    assert len(results) == 1
    assert results[0].requirement.requirement_id == "R24"
    assert results[0].status == CheckStatus.FAIL
    assert "Missing prothon-doc-harmonizer skill" in str(results[0].rationale)
