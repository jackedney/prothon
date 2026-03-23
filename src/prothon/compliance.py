from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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


def analyze_python_file(path: Path) -> dict[str, Any]:
    """Analyze a Python file for imports and base classes using AST.

    Args:
        path: Path to the Python file.

    Returns:
        Dictionary with 'imports' (set) and 'base_classes' (dict).
    """
    if not path.exists():
        return {"imports": set(), "base_classes": {}}

    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return {"imports": set(), "base_classes": {}}

    results: dict[str, Any] = {
        "imports": set(),
        "base_classes": {},
    }

    for node in ast.walk(tree):
        _collect_metadata(node, results)

    return results


def _collect_metadata(node: ast.AST, results: dict[str, Any]) -> None:
    """Helper to collect imports and base classes from an AST node."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            results["imports"].add(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            results["imports"].add(node.module)
    elif isinstance(node, ast.ClassDef):
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
        results["base_classes"][node.name] = bases


def check_patterns_doc(patterns_path: Path) -> list[CheckResult]:
    """Verify PATTERNS.md code blocks follow R25-R26 rules.

    Args:
        patterns_path: Path to PATTERNS.md.

    Returns:
        List of CheckResult for R25 and R26.
    """
    results = []
    r25 = Requirement(
        source="SPEC",
        requirement_id="R25",
        statement="PATTERNS.md rationale expressed in natural language, not code.",
    )
    r26 = Requirement(
        source="SPEC",
        requirement_id="R26",
        statement="PATTERNS.md code examples limited to signatures only.",
    )

    if not patterns_path.exists():
        results.append(
            CheckResult(r25, CheckStatus.SKIP, rationale="PATTERNS.md missing")
        )
        results.append(
            CheckResult(r26, CheckStatus.SKIP, rationale="PATTERNS.md missing")
        )
        return results

    content = patterns_path.read_text()
    code_blocks = _extract_python_blocks(content)

    if not code_blocks:
        results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(patterns_path)))
        results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(patterns_path)))
        return results

    # R25: Heuristic check for rationale (ensure some natural language exists)
    if _is_code_dominant(content, code_blocks):
        results.append(
            CheckResult(
                r25,
                CheckStatus.FAIL,
                evidence=f"{patterns_path}:1",
                rationale="Code blocks dominate PATTERNS.md; rationale should be natural language.",
            )
        )
    else:
        results.append(CheckResult(r25, CheckStatus.PASS, evidence=str(patterns_path)))

    # R26: Signature-only check
    for line_no, block in code_blocks:
        if not _is_signature_only(block):
            results.append(
                CheckResult(
                    r26,
                    CheckStatus.FAIL,
                    evidence=f"{patterns_path}:{line_no}",
                    rationale="Code block contains implementation logic or imports.",
                )
            )
            break
    else:
        results.append(CheckResult(r26, CheckStatus.PASS, evidence=str(patterns_path)))

    return results


def _is_code_dominant(content: str, code_blocks: list[tuple[int, str]]) -> bool:
    """Heuristic to check if code blocks dominate the document."""
    text_len = len(content)
    code_len = sum(len(block) for _, block in code_blocks)
    return code_len > text_len * 0.7  # 70% threshold


def _extract_python_blocks(content: str) -> list[tuple[int, str]]:
    """Extract python code blocks with start line numbers."""
    blocks = []
    pattern = re.compile(r"```python\s+(.*?)```", re.DOTALL)
    for match in pattern.finditer(content):
        line_no = content.count("\n", 0, match.start()) + 1
        blocks.append((line_no, match.group(1)))
    return blocks


def _is_signature_only(code: str) -> bool:
    """Check if Python code contains only signatures."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in tree.body:
        if not _is_signature_node(node):
            return False
    return True


def _is_signature_node(node: ast.AST) -> bool:
    """Verify a node is a signature-only definition."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _is_func_signature(node)
    if isinstance(node, ast.ClassDef):
        for n in node.body:
            if isinstance(n, ast.Pass):
                continue
            if (
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant)
                and (isinstance(n.value.value, str) or n.value.value is Ellipsis)
            ):
                continue
            if not _is_signature_node(n):
                return False
        return True
    return False


def _is_func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Verify function body contains only docstring, pass, or ellipsis."""
    for stmt in node.body:
        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Constant) and (
                isinstance(stmt.value.value, str) or stmt.value.value is Ellipsis
            ):
                continue
        if isinstance(stmt, ast.Pass):
            continue
        return False
    return True


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

    for res in report.results:
        res.check_type = CheckType.STATIC

    return report


def check_package_structure(root: Path) -> list[CheckResult]:
    """Verify src/ layout and py.typed existence (SPEC R3)."""
    results = []
    req = Requirement(
        source="SPEC",
        requirement_id="R3",
        statement="Project must use src/ layout with a typed package (py.typed).",
    )

    src_dir = root / "src"
    if not src_dir.is_dir():
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence="src/",
                rationale="Missing src/ directory.",
            )
        )
        return results

    # Try to find a package directory with py.typed
    packages = [
        p for p in src_dir.iterdir() if p.is_dir() and (p / "__init__.py").exists()
    ]
    if not packages:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence="src/",
                rationale="No Python packages found in src/.",
            )
        )
        return results

    for pkg in packages:
        py_typed = pkg / "py.typed"
        if py_typed.exists():
            results.append(CheckResult(req, CheckStatus.PASS, evidence=str(py_typed)))
            return results

    results.append(
        CheckResult(
            req,
            CheckStatus.FAIL,
            evidence=str(packages[0]),
            rationale=f"Missing py.typed marker in {packages[0].name} package.",
        )
    )
    return results


def check_pre_commit(root: Path) -> list[CheckResult]:
    """Verify pre-commit hooks existence (SPEC R5)."""
    results = []
    req = Requirement(
        source="SPEC",
        requirement_id="R5",
        statement="Project must include pre-commit hooks configuration.",
    )
    pc_path = root / ".pre-commit-config.yaml"
    if pc_path.is_file():
        results.append(CheckResult(req, CheckStatus.PASS, evidence=str(pc_path)))
    else:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=".pre-commit-config.yaml",
                rationale="Missing pre-commit config.",
            )
        )
    return results


def check_skills_dir(root: Path) -> list[CheckResult]:
    """Verify project-specific skills directory existence (SPEC R15)."""
    results = []
    req = Requirement(
        source="SPEC",
        requirement_id="R15",
        statement="Project must have a .agents/skills/ directory for project-specific reference skills.",
    )
    skills_dir = root / ".agents" / "skills"
    if skills_dir.is_dir():
        results.append(CheckResult(req, CheckStatus.PASS, evidence=str(skills_dir)))
    else:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=".agents/skills/",
                rationale="Missing project skills directory.",
            )
        )
    return results


def check_doc_existence(root: Path) -> list[CheckResult]:
    """Verify SPEC.md, DESIGN.md, and PATTERNS.md exist."""
    results = []
    doc_reqs = [
        ("SPEC.md", "R18", "SPEC"),
        ("DESIGN.md", "R20", "SPEC"),
        ("PATTERNS.md", "R20", "SPEC"),
    ]
    for doc, req_id, source in doc_reqs:
        req = Requirement(
            source=source,
            requirement_id=req_id,
            statement=f"Prerequisite document {doc} must exist.",
        )
        doc_path = root / "docs" / doc
        if doc_path.is_file():
            results.append(CheckResult(req, CheckStatus.PASS, evidence=str(doc_path)))
        else:
            results.append(
                CheckResult(
                    req,
                    CheckStatus.FAIL,
                    evidence=f"docs/{doc}",
                    rationale="Required document is missing.",
                )
            )
    return results


def check_inheritance(root: Path) -> list[CheckResult]:
    """Verify all custom exceptions inherit from ProthonError."""
    results = []
    exc_path = root / "src" / "prothon" / "exceptions.py"
    if not exc_path.is_file():
        return results

    req = Requirement(
        source="DESIGN",
        statement="All domain exceptions must inherit from ProthonError.",
    )
    analysis = analyze_python_file(exc_path)
    violations = [
        name
        for name, bases in analysis.get("base_classes", {}).items()
        if name != "ProthonError" and "ProthonError" not in bases
    ]

    if not violations:
        results.append(CheckResult(req, CheckStatus.PASS, evidence=str(exc_path)))
    else:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=f"{exc_path}:1",
                rationale=f"Exceptions not inheriting from ProthonError: {', '.join(violations)}",
            )
        )
    return results


def check_agent_files(root: Path) -> list[CheckResult]:
    """Verify AGENTS.md and its expected symlinks."""
    results = []
    for filename in ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "AGENT.md"]:
        req = Requirement(
            source="DESIGN",
            requirement_id="R4",
            statement=f"Project must have {filename}.",
        )
        file_path = root / filename
        if not file_path.exists():
            results.append(CheckResult(req, CheckStatus.FAIL, evidence=filename))
            continue

        if filename != "AGENTS.md":
            if not file_path.is_symlink():
                results.append(
                    CheckResult(
                        req,
                        CheckStatus.FAIL,
                        evidence=filename,
                        rationale=f"{filename} must be a symlink to AGENTS.md.",
                    )
                )
                continue
            target = file_path.resolve()
            expected = (root / "AGENTS.md").resolve()
            if target != expected:
                results.append(
                    CheckResult(
                        req,
                        CheckStatus.FAIL,
                        evidence=filename,
                        rationale=f"{filename} symlink points to {target}, expected {expected}.",
                    )
                )
                continue
        results.append(CheckResult(req, CheckStatus.PASS, evidence=str(file_path)))
    return results
