from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prothon.refactor.models import DriftFinding
from prothon.refactor.promise_gen import generate_refactor_promise


def test_generate_refactor_promise_field_mapping(tmp_path: Path):
    existing = tmp_path / "e.py"
    existing.write_text("x")
    findings = [
        DriftFinding(
            title="Fix X",
            rationale="Too big",
            doc_sections=["DESIGN.md"],
            files_affected=[existing, tmp_path / "n.py"],
        )
    ]
    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        t = generate_refactor_promise(tmp_path, findings).tasks[0]
    assert t.title == "Fix X"
    assert t.goal == "Too big"
    assert "Fix X" in t.success_criteria
    assert "e.py" in t.files_to_modify
    assert "n.py" in t.files_to_create
    assert t.doc_sections == ["DESIGN.md"]


def test_generate_refactor_promise_ordering_by_doc_sections(tmp_path: Path):
    code = DriftFinding(title="Code", rationale="r", doc_sections=[])
    pat = DriftFinding(title="Pat", rationale="r", doc_sections=["PATTERNS.md"])
    des = DriftFinding(title="Des", rationale="r", doc_sections=["DESIGN.md"])
    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="a"):
        titles = [
            t.title for t in generate_refactor_promise(tmp_path, [code, pat, des]).tasks
        ]
    assert titles.index("Des") < titles.index("Code")
    assert titles.index("Pat") < titles.index("Code")


def test_generate_refactor_promise_no_doc_sections_last(tmp_path: Path):
    with_doc = DriftFinding(title="Doc", rationale="r", doc_sections=["SPEC.md"])
    no_doc = DriftFinding(title="Bare", rationale="r", doc_sections=[])
    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="a"):
        titles = [
            t.title
            for t in generate_refactor_promise(tmp_path, [no_doc, with_doc]).tasks
        ]
    assert titles.index("Doc") < titles.index("Bare")


def test_generate_refactor_promise_metadata(tmp_path: Path):
    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="beef"):
        p = generate_refactor_promise(tmp_path, [])
    assert p.metadata.base_commit == "beef"
    assert p.metadata.created_at.endswith("Z")
