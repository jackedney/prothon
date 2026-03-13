from __future__ import annotations

from pathlib import Path

from prothon.refactor import DriftFinding, discover_drift, generate_refactor_promise


def test_discover_drift_missing_docs(tmp_path: Path):
    """Test that discover_drift identifies missing core documentation."""
    # Empty project root
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]

    assert "Missing SPEC.md" in titles
    # DESIGN and PATTERNS depend on SPEC existing in the current implementation
    assert "Missing DESIGN.md" not in titles


def test_discover_drift_docs_hierarchy(tmp_path: Path):
    """Test the sequential discovery of missing docs."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SPEC.md").write_text("# SPEC")

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing DESIGN.md" in titles
    assert "Missing PATTERNS.md" not in titles

    (docs / "DESIGN.md").write_text("# DESIGN")
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing PATTERNS.md" in titles


def test_discover_drift_large_files(tmp_path: Path):
    """Test identification of files exceeding line limit."""
    src = tmp_path / "src"
    src.mkdir()
    large_file = src / "too_long.py"
    large_file.write_text("\n" * 501)

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Large file: too_long.py" in titles


def test_discover_drift_missing_tests(tmp_path: Path):
    """Test identification of source files missing tests."""
    src = tmp_path / "src" / "prothon"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()

    module = src / "new_feature.py"
    module.write_text("def feat(): pass")

    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for new_feature.py" in titles

    # After adding test, it should be gone
    (tests / "test_new_feature.py").write_text("def test_feat(): pass")
    findings = discover_drift(tmp_path)
    titles = [f.title for f in findings]
    assert "Missing tests for new_feature.py" not in titles


def test_generate_refactor_promise(tmp_path: Path):
    """Test creating a promise from drift findings."""
    finding = DriftFinding(
        title="Test Finding",
        rationale="Test Rationale",
        doc_sections=["Section"],
        files_affected=[tmp_path / "affected.py"],
    )

    promise = generate_refactor_promise(tmp_path, [finding])

    assert len(promise.tasks) == 1
    task = promise.tasks[0]
    assert task.title == "Test Finding"
    assert task.goal == "Test Rationale"
    assert "affected.py" in task.files_to_create  # Doesn't exist yet
