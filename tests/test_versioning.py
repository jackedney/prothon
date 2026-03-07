"""Tests for versioning module."""

from __future__ import annotations


import pytest

from prothon.exceptions import VersionError
from prothon.git import rev_parse_head, run_git
from prothon.versioning import (
    bump_major,
    bump_minor,
    bump_patch,
    create_tag,
    detect_bump_type,
    parse_version,
    update_init_version,
    update_pyproject_version,
)


def test_parse_version_extracts_components():
    assert parse_version("1.2.3") == (1, 2, 3)


def test_parse_version_handles_v_prefix():
    assert parse_version("v2.0.0") == (2, 0, 0)


def test_parse_version_rejects_invalid():
    with pytest.raises(VersionError, match="invalid version"):
        parse_version("not-a-version")


def test_parse_version_rejects_missing_patch():
    with pytest.raises(VersionError, match="invalid version"):
        parse_version("1.2")


@pytest.mark.parametrize("v", ["1.2.3.4", "1.2.3-rc1", "v1.2.3x"])
def test_parse_version_rejects_trailing_characters(v):
    with pytest.raises(VersionError, match="invalid version"):
        parse_version(v)


@pytest.mark.parametrize(
    "v,expected",
    [
        ("0.0.1", (0, 0, 1)),
        ("10.20.30", (10, 20, 30)),
        ("v0.1.0", (0, 1, 0)),
    ],
)
def test_parse_version_parametrized(v, expected):
    assert parse_version(v) == expected


def test_bump_major_resets_minor_and_patch():
    assert bump_major("1.2.3") == "2.0.0"


def test_bump_major_from_zero():
    assert bump_major("0.5.7") == "1.0.0"


def test_bump_major_with_v_prefix():
    assert bump_major("v3.9.2") == "4.0.0"


def test_bump_minor_resets_patch():
    assert bump_minor("1.2.3") == "1.3.0"


def test_bump_minor_from_zero():
    assert bump_minor("2.0.5") == "2.1.0"


def test_bump_minor_with_v_prefix():
    assert bump_minor("v1.0.0") == "1.1.0"


def test_bump_patch_increments_patch():
    assert bump_patch("1.2.3") == "1.2.4"


def test_bump_patch_from_zero():
    assert bump_patch("0.0.0") == "0.0.1"


def test_bump_patch_with_v_prefix():
    assert bump_patch("v2.1.0") == "2.1.1"


def test_update_pyproject_updates_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n')
    update_pyproject_version(pyproject, "0.2.0")
    content = pyproject.read_text()
    assert 'version = "0.2.0"' in content


def test_update_pyproject_preserves_comments(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n# comment\n')
    update_pyproject_version(pyproject, "0.2.0")
    content = pyproject.read_text()
    assert 'version = "0.2.0"' in content
    assert "# comment" in content


def test_update_pyproject_preserves_other_tables(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nversion = "0.1.0"\n[tool.ruff]\nline-length = 88\n'
    )
    update_pyproject_version(pyproject, "0.2.0")
    content = pyproject.read_text()
    assert "[tool.ruff]" in content
    assert "line-length = 88" in content


def test_update_pyproject_raises_on_missing_project_table(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff]\nline-length = 88\n")
    with pytest.raises(VersionError, match="pyproject.toml missing \\[project] table"):
        update_pyproject_version(pyproject, "0.2.0")


def test_update_pyproject_raises_on_invalid_toml(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("not valid toml [")
    with pytest.raises(VersionError, match="failed to update pyproject.toml"):
        update_pyproject_version(pyproject, "0.2.0")


def test_update_init_version_updates_double_quotes(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "0.1.0"\n')
    update_init_version(init, "0.2.0")
    assert '__version__ = "0.2.0"' in init.read_text()


def test_update_init_version_updates_single_quotes(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text("__version__ = '0.1.0'\n")
    update_init_version(init, "0.2.0")
    assert '__version__ = "0.2.0"' in init.read_text()


def test_update_init_version_handles_whitespace(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__version__  =  "0.1.0"\n')
    update_init_version(init, "0.2.0")
    assert '__version__ = "0.2.0"' in init.read_text()


def test_update_init_version_preserves_other_content(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text(
        '"""Module docstring."""\n__version__ = "0.1.0"\n\ndef foo(): pass\n'
    )
    update_init_version(init, "0.2.0")
    content = init.read_text()
    assert '__version__ = "0.2.0"' in content
    assert "Module docstring" in content
    assert "def foo(): pass" in content


def test_update_init_version_raises_when_no_version(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('"""Module docstring."""\n')
    with pytest.raises(VersionError, match="no __version__ assignment"):
        update_init_version(init, "0.2.0")


def test_create_tag_creates_annotated_tag(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# test\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)

    create_tag("1.0.0", cwd=tmp_path)

    tags = run_git("tag", "-l", cwd=tmp_path).strip()
    assert "v1.0.0" in tags

    tag_info = run_git("tag", "-l", "-n1", "v1.0.0", cwd=tmp_path)
    assert "release 1.0.0" in tag_info


def test_create_tag_uses_v_prefix(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# test\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)

    create_tag("2.3.4", cwd=tmp_path)

    tags = run_git("tag", "-l", cwd=tmp_path).strip()
    assert tags == "v2.3.4"


def test_detect_bump_type_returns_major_for_spec_change(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# spec\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "docs" / "SPEC.md").write_text("# updated\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "spec change", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "major"


def test_detect_bump_type_returns_minor_for_design_change(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DESIGN.md").write_text("# design\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "docs" / "DESIGN.md").write_text("# updated\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "design change", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "minor"


def test_detect_bump_type_returns_patch_for_patterns_change(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PATTERNS.md").write_text("# patterns\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "docs" / "PATTERNS.md").write_text("# updated\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "patterns change", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "patch"


def test_detect_bump_type_returns_patch_for_source_change(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "src" / "main.py").write_text("print('updated')\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "source change", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "patch"


def test_detect_bump_type_returns_none_for_readme_only(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# readme\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "README.md").write_text("# updated\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "readme update", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) is None


def test_detect_bump_type_prioritizes_spec_over_design(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# spec\n")
    (tmp_path / "docs" / "DESIGN.md").write_text("# design\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "docs" / "SPEC.md").write_text("# spec updated\n")
    (tmp_path / "docs" / "DESIGN.md").write_text("# design updated\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "both changed", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "major"


def test_detect_bump_type_prioritizes_design_over_patterns(tmp_path):
    run_git("init", cwd=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DESIGN.md").write_text("# design\n")
    (tmp_path / "docs" / "PATTERNS.md").write_text("# patterns\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test", cwd=tmp_path)
    run_git("commit", "-m", "initial", cwd=tmp_path)
    before = rev_parse_head(cwd=tmp_path)

    (tmp_path / "docs" / "DESIGN.md").write_text("# design updated\n")
    (tmp_path / "docs" / "PATTERNS.md").write_text("# patterns updated\n")
    run_git("add", ".", cwd=tmp_path)
    run_git("commit", "-m", "both changed", cwd=tmp_path)
    after = rev_parse_head(cwd=tmp_path)

    assert detect_bump_type(before, after, cwd=tmp_path) == "minor"
