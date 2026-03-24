from pathlib import Path

from prothon.compliance import CheckStatus
from prothon.checks import check_semantic_versioning


def test_check_semantic_versioning_pass(tmp_path: Path) -> None:
    template_dir = tmp_path / "template"
    github_dir = template_dir / ".github" / "workflows"
    github_dir.mkdir(parents=True)

    (github_dir / "version-bump.yml.jinja").write_text("")
    (github_dir / "version-tag.yml.jinja").write_text("")
    (template_dir / ".gitlab-ci.yml.jinja").write_text("")

    results = check_semantic_versioning(tmp_path)

    assert len(results) == 2

    r53_res = next(r for r in results if r.requirement.requirement_id == "R53")
    r55_res = next(r for r in results if r.requirement.requirement_id == "R55")

    assert r53_res.status == CheckStatus.PASS
    assert r55_res.status == CheckStatus.PASS


def test_check_semantic_versioning_fail_missing_some(tmp_path: Path) -> None:
    template_dir = tmp_path / "template"
    github_dir = template_dir / ".github" / "workflows"
    github_dir.mkdir(parents=True)

    # Missing gitlab and version-tag
    (github_dir / "version-bump.yml.jinja").write_text("")

    results = check_semantic_versioning(tmp_path)

    assert len(results) == 2
    r53_res = next(r for r in results if r.requirement.requirement_id == "R53")
    r55_res = next(r for r in results if r.requirement.requirement_id == "R55")

    assert r53_res.status == CheckStatus.FAIL
    assert r55_res.status == CheckStatus.FAIL

    assert "version-tag.yml.jinja" in str(r53_res.rationale)
    assert ".gitlab-ci.yml.jinja" in str(r53_res.rationale)


def test_check_semantic_versioning_fail_missing_all(tmp_path: Path) -> None:
    results = check_semantic_versioning(tmp_path)

    assert len(results) == 2
    r53_res = next(r for r in results if r.requirement.requirement_id == "R53")
    r55_res = next(r for r in results if r.requirement.requirement_id == "R55")

    assert r53_res.status == CheckStatus.FAIL
    assert r55_res.status == CheckStatus.FAIL
