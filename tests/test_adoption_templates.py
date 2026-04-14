"""Tests for adoption_templates module."""

from __future__ import annotations


from prothon.adoption_templates import (
    _DESIGN_SCAFFOLD,
    _PATTERNS_SCAFFOLD,
    _REFERENCES_MODULES_HEADER,
    _SPEC_SCAFFOLD,
    get_agents_content,
    get_gitlab_version_bump,
    get_version_bump_workflow,
    get_version_tag_workflow,
)


def test_spec_scaffold_has_required_sections():
    for heading in ("Purpose", "Requirements", "Constraints", "Out of Scope"):
        assert f"## {heading}" in _SPEC_SCAFFOLD


def test_design_scaffold_has_required_sections():
    for heading in (
        "Architecture",
        "Technology Choices",
        "Interfaces",
        "Key Decisions",
    ):
        assert f"## {heading}" in _DESIGN_SCAFFOLD


def test_patterns_scaffold_has_required_sections():
    for heading in (
        "Code Organization",
        "Design Patterns",
        "Error Handling",
        "Testing Patterns",
    ):
        assert f"## {heading}" in _PATTERNS_SCAFFOLD


def test_references_modules_header_mentions_r25():
    assert "R25-R26" in _REFERENCES_MODULES_HEADER


def test_get_version_bump_workflow_returns_yaml():
    content = get_version_bump_workflow()
    assert "version" in content
    assert "jobs:" in content or "stages:" not in content


def test_get_version_tag_workflow_returns_yaml():
    content = get_version_tag_workflow()
    assert "version" in content


def test_get_gitlab_version_bump_returns_yaml():
    content = get_gitlab_version_bump()
    assert "stages:" in content


def test_get_agents_content_returns_markdown():
    content = get_agents_content()
    assert len(content) > 50
    assert "#" in content
