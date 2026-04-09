from __future__ import annotations

from pathlib import Path

from prothon.checks.adoption import check_adoption_intelligence
from prothon.checks.docs import (
    check_doc_existence,
    check_doc_harmonizer,
    check_patterns_doc,
    check_progressive_disclosure,
)
from prothon.checks.research import check_semantic_versioning, check_tech_researcher
from prothon.checks.structure import (
    check_agent_files,
    check_inheritance,
    check_package_structure,
    check_pre_commit,
    check_skills_dir,
)
from prothon.checks.utils import analyze_python_file
from prothon.checks.workflows import (
    check_execute_logic,
    check_refactor_logic,
)
from prothon.compliance import (
    CheckType,
    ComplianceReport,
)

__all__ = [
    "analyze_python_file",
    "check_adoption_intelligence",
    "check_agent_files",
    "check_doc_existence",
    "check_doc_harmonizer",
    "check_execute_logic",
    "check_inheritance",
    "check_package_structure",
    "check_patterns_doc",
    "check_pre_commit",
    "check_progressive_disclosure",
    "check_refactor_logic",
    "check_semantic_versioning",
    "check_skills_dir",
    "check_tech_researcher",
    "run_static_checks",
]


def run_static_checks(root: Path) -> ComplianceReport:
    """Run all deterministic static compliance checks."""
    report = ComplianceReport()

    # R25, R26: PATTERNS.md code blocks
    patterns_path = root / "docs" / "PATTERNS.md"
    report.results.extend(check_patterns_doc(patterns_path))

    report.results.extend(check_doc_existence(root))
    report.results.extend(check_inheritance(root))
    report.results.extend(check_agent_files(root))
    report.results.extend(check_package_structure(root))
    report.results.extend(check_pre_commit(root))
    report.results.extend(check_skills_dir(root))
    report.results.extend(check_adoption_intelligence(root))
    report.results.extend(check_execute_logic(root))
    report.results.extend(check_refactor_logic(root))
    report.results.extend(check_tech_researcher(root))
    report.results.extend(check_doc_harmonizer(root))
    report.results.extend(check_progressive_disclosure(root))
    report.results.extend(check_semantic_versioning(root))

    for res in report.results:
        res.check_type = CheckType.STATIC

    return report
