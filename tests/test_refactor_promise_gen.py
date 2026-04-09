from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prothon.refactor.models import DriftCategory, DriftFinding, Severity
from prothon.refactor.promise_gen import generate_refactor_promise


def test_generate_refactor_promise_field_mapping(tmp_path: Path):
    existing = tmp_path / "existing.py"
    existing.write_text("# content")
    new_file = tmp_path / "new.py"

    findings = [
        DriftFinding(
            title="Fix large file",
            rationale="File exceeds threshold",
            doc_sections=["DESIGN.md"],
            files_affected=[existing, new_file],
        )
    ]

    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc123"):
        promise = generate_refactor_promise(tmp_path, findings)

    task = promise.tasks[0]
    assert task.title == "Fix large file"
    assert task.goal == "File exceeds threshold"
    assert "Fix large file" in task.success_criteria
    assert "existing.py" in task.files_to_modify
    assert "new.py" in task.files_to_create
    assert task.doc_sections == ["DESIGN.md"]


def test_generate_refactor_promise_ordering_by_doc_sections(tmp_path: Path):
    code_finding = DriftFinding(
        title="Code issue",
        rationale="Fix code",
        category=DriftCategory.LARGE_FILES,
        severity=Severity.MEDIUM,
        doc_sections=[],
    )
    patterns_finding = DriftFinding(
        title="Patterns issue",
        rationale="Fix patterns",
        category=DriftCategory.PATTERNS_COMPLIANCE,
        severity=Severity.LOW,
        doc_sections=["PATTERNS.md"],
    )
    design_finding = DriftFinding(
        title="Design issue",
        rationale="Fix design",
        category=DriftCategory.DOC_HIERARCHY,
        severity=Severity.HIGH,
        doc_sections=["DESIGN.md"],
    )

    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(
            tmp_path, [code_finding, patterns_finding, design_finding]
        )

    titles = [t.title for t in promise.tasks]
    design_idx = titles.index("Design issue")
    patterns_idx = titles.index("Patterns issue")
    code_idx = titles.index("Code issue")
    assert design_idx < code_idx
    assert patterns_idx < code_idx


def test_generate_refactor_promise_no_doc_sections_come_last(tmp_path: Path):
    doc_finding = DriftFinding(
        title="Doc finding",
        rationale="Has docs",
        doc_sections=["SPEC.md"],
    )
    bare_finding = DriftFinding(
        title="Bare finding",
        rationale="No docs",
        doc_sections=[],
    )

    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, [bare_finding, doc_finding])

    titles = [t.title for t in promise.tasks]
    assert titles.index("Doc finding") < titles.index("Bare finding")


def test_generate_refactor_promise_metadata_has_base_commit(tmp_path: Path):
    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="deadbeef"):
        promise = generate_refactor_promise(tmp_path, [])

    assert promise.metadata.base_commit == "deadbeef"


def test_generate_refactor_promise_metadata_has_created_at(tmp_path: Path):
    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, [])

    assert promise.metadata.created_at != ""
    assert promise.metadata.created_at.endswith("Z")


def test_generate_refactor_promise_doc_sections_propagated(tmp_path: Path):
    findings = [
        DriftFinding(
            title="Test",
            rationale="Reason",
            doc_sections=["SPEC.md", "DESIGN.md"],
        )
    ]

    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, findings)

    assert promise.tasks[0].doc_sections == ["SPEC.md", "DESIGN.md"]


def test_generate_refactor_promise_success_criteria_contains_title(tmp_path: Path):
    findings = [
        DriftFinding(
            title="Missing SPEC.md",
            rationale="SPEC.md must exist",
        )
    ]

    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, findings)

    assert "Missing SPEC.md" in promise.tasks[0].success_criteria


def test_generate_refactor_promise_files_outside_root_ignored(tmp_path: Path):
    outside = Path("/some/other/path/file.py")
    findings = [
        DriftFinding(
            title="Outside",
            rationale="File outside project",
            files_affected=[outside],
        )
    ]

    with patch("prothon.refactor.promise_gen.rev_parse_head", return_value="abc"):
        promise = generate_refactor_promise(tmp_path, findings)

    task = promise.tasks[0]
    assert task.files_to_modify == []
    assert task.files_to_create == []
