from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(Enum):
    """Tri-state status for a compliance check.

    Matches the verification status used in the promise system but scoped
    to documentation-to-code alignment.
    """

    PASS = "PASS"  # nosec
    FAIL = "FAIL"
    SKIP = "SKIP"


class CheckType(Enum):
    """The method used to verify a requirement."""

    STATIC = "STATIC"
    SEMANTIC = "SEMANTIC"


@dataclass
class Requirement:
    """A checkable requirement extracted from project documentation.

    Each requirement corresponds to a numbered rule in SPEC, an architectural
    decision in DESIGN, or a coding pattern in PATTERNS.

    Attributes:
        source: The documentation level ("SPEC", "DESIGN", or "PATTERNS").
        statement: The normative text of the requirement.
        requirement_id: Optional identifier (e.g., "R1" for SPEC).
    """

    source: str
    statement: str
    requirement_id: str | None = None


@dataclass
class CheckResult:
    """The result of verifying a single requirement against implementation.

    Carries the evidence mapping and rationale required by the compliance
    audit workflow.

    Attributes:
        requirement: The requirement being checked.
        status: The outcome of the check (PASS, FAIL, or SKIP).
        check_type: The method used for verification (STATIC or SEMANTIC).
        evidence: File and line number where compliance (or violation) is found.
        rationale: Brief explanation of the finding.
    """

    requirement: Requirement
    status: CheckStatus
    check_type: CheckType = CheckType.STATIC
    evidence: str = ""
    rationale: str = ""

    def __str__(self) -> str:
        """Return a single-line summary of the result."""
        id_str = (
            f" [{self.requirement.requirement_id}]"
            if self.requirement.requirement_id
            else ""
        )
        source = self.requirement.source
        statement = self.requirement.statement[:50]
        summary = (
            f"{self.status.value:4s} | {self.check_type.value:8s} | "
            f"{source}{id_str}: {statement}..."
        )
        return f"{summary} ({self.evidence})"

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a dictionary for subagent aggregation."""
        return {
            "requirement": {
                "source": self.requirement.source,
                "statement": self.requirement.statement,
                "requirement_id": self.requirement.requirement_id,
            },
            "status": self.status.value,
            "check_type": self.check_type.value,
            "evidence": self.evidence,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckResult":
        """Create a CheckResult from a dictionary (e.g., from subagent JSON)."""
        req_data = data["requirement"]
        req = Requirement(
            source=req_data["source"],
            statement=req_data["statement"],
            requirement_id=req_data.get("requirement_id"),
        )
        return cls(
            requirement=req,
            status=CheckStatus(data["status"]),
            check_type=CheckType(data.get("check_type", "STATIC")),
            evidence=data.get("evidence", ""),
            rationale=data.get("rationale", ""),
        )


@dataclass
class ComplianceReport:
    """Collection of compliance findings across all documentation levels.

    Aggregates results for reporting via the CLI and serves as the data
    source for compliance verification gates.

    Attributes:
        results: A list of individual check results.
    """

    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if the report contains no failures."""
        return not any(r.status == CheckStatus.FAIL for r in self.results)

    @property
    def score(self) -> float:
        """Return the percentage of passing checks (excluding SKIP).

        The score represents the architectural integrity of the project
        based on verifiable requirements.
        """
        relevant = [r for r in self.results if r.status != CheckStatus.SKIP]
        if not relevant:
            return 100.0
        passing = sum(1 for r in relevant if r.status == CheckStatus.PASS)
        return (passing / len(relevant)) * 100.0

    @property
    def failures(self) -> list[CheckResult]:
        """Return all results that failed the compliance check."""
        return [r for r in self.results if r.status == CheckStatus.FAIL]

    def results_by_source(self, source: str) -> list[CheckResult]:
        """Filter results by source documentation level (e.g., 'SPEC')."""
        return [r for r in self.results if r.requirement.source == source]

    def results_by_type(self, check_type: CheckType) -> list[CheckResult]:
        """Filter results by check type (e.g., STATIC or SEMANTIC)."""
        return [r for r in self.results if r.check_type == check_type]

    @property
    def static_results(self) -> list[CheckResult]:
        """Return results from static checks."""
        return self.results_by_type(CheckType.STATIC)

    @property
    def semantic_results(self) -> list[CheckResult]:
        """Return results from semantic checks."""
        return self.results_by_type(CheckType.SEMANTIC)

    def merge(self, other: "ComplianceReport") -> None:
        """Merge results from another compliance report."""
        self.results.extend(other.results)

    def add_from_dicts(self, findings: list[dict[str, Any]]) -> None:
        """Aggregate results from a list of finding dictionaries."""
        for finding in findings:
            self.results.append(CheckResult.from_dict(finding))

    def format_summary(self) -> str:
        """Return a pretty-printed summary of the compliance status.

        Provides a high-level overview of the project's health across
        all documentation layers.
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == CheckStatus.PASS)
        failed = len(self.failures)
        skipped = sum(1 for r in self.results if r.status == CheckStatus.SKIP)

        lines = [
            "COMPLIANCE SUMMARY",
            f"Overall Score: {self.score:.1f}%",
            f"Checks: {total} (PASS: {passed}, FAIL: {failed}, SKIP: {skipped})",
            "",
        ]

        if self.passed:
            lines.append("All requirements met. System is compliant.")
        else:
            lines.append(f"Found {failed} compliance violations.")
            lines.append("Action Items:")
            for failure in self.failures:
                source = failure.requirement.source
                statement = failure.requirement.statement[:60]
                lines.append(f"  - [{source}] {statement}")

        return "\n".join(lines)
