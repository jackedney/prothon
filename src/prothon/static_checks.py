from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    CheckType,
    ComplianceReport,
    Requirement,
)


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
    report.results.extend(check_adoption_intelligence(root))
    report.results.extend(check_execute_logic(root))
    report.results.extend(check_refactor_logic(root))
    report.results.extend(check_tech_researcher(root))

    for res in report.results:
        res.check_type = CheckType.STATIC

    return report


def check_adoption_intelligence(root: Path) -> list[CheckResult]:
    """Verify Adoption Intelligence implementation (SPEC R13)."""
    results = []
    req = Requirement(
        source="SPEC",
        requirement_id="R13",
        statement="Project adoption must use AST analysis to pre-populate PATTERNS.md.",
    )

    miner_path = root / "src" / "prothon" / "ast_miner.py"
    scaffold_path = root / "src" / "prothon" / "scaffold.py"
    adoption_path = root / "src" / "prothon" / "adoption.py"

    if not miner_path.exists():
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence="src/prothon/ast_miner.py",
                rationale="Missing ASTPatternMiner implementation.",
            )
        )
        return results

    # R13 is now implemented in adoption.py after split
    target_path = adoption_path if adoption_path.exists() else scaffold_path

    if not target_path.exists():
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"Missing {target_path.name} to integrate ASTPatternMiner.",
            )
        )
        return results

    analysis = analyze_python_file(target_path)
    imports = analysis.get("imports", set())

    # Check for direct or from-import
    if "prothon.ast_miner" not in imports and "ast_miner" not in imports:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} does not import ASTPatternMiner.",
            )
        )
        return results

    # Check for usage in the file
    content = target_path.read_text()
    if "ASTPatternMiner()" not in content:
        results.append(
            CheckResult(
                req,
                CheckStatus.FAIL,
                evidence=str(target_path),
                rationale=f"{target_path.name} imports but does not appear to use ASTPatternMiner.",
            )
        )
        return results

    results.append(CheckResult(req, CheckStatus.PASS, evidence=str(target_path)))
    return results


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


def check_execute_logic(root: Path) -> list[CheckResult]:
    """Verify Execute workflow implementation (SPEC R27-R33)."""
    results = []
    promise_path = root / "src" / "prothon" / "promise.py"
    verify_path = root / "src" / "prothon" / "promise_verify.py"
    execute_skill = root / "src" / "prothon" / "skills" / "prothon-execute" / "SKILL.md"

    results.extend(_check_execute_plan_model(promise_path))
    results.extend(_check_execute_verification(verify_path))
    results.extend(_check_execute_workflow(execute_skill))
    return results


def _check_execute_plan_model(promise_path: Path) -> list[CheckResult]:
    """Check R27 and R28 in promise.py."""
    results = []
    req_map = {
        "R27": "System must provide execute workflow generating a plan of tasks.",
        "R28": "Tasks must declare files to touch and line counts.",
    }
    if not promise_path.exists():
        return results

    content = promise_path.read_text()
    if "def plan" in content:
        results.append(
            CheckResult(
                Requirement("SPEC", req_map["R27"], "R27"),
                CheckStatus.PASS,
                evidence=str(promise_path),
            )
        )
    if "expected_lines_added" in content and "files_to_modify" in content:
        results.append(
            CheckResult(
                Requirement("SPEC", req_map["R28"], "R28"),
                CheckStatus.PASS,
                evidence=str(promise_path),
            )
        )
    return results


def _check_execute_verification(verify_path: Path) -> list[CheckResult]:
    """Check R31 in promise_verify.py."""
    results = []
    req_statement = "System must verify actual changes against declared plan."
    if not verify_path.exists():
        return results

    content = verify_path.read_text()
    if "check_task" in content and "actual_added" in content:
        results.append(
            CheckResult(
                Requirement("SPEC", req_statement, "R31"),
                CheckStatus.PASS,
                evidence=str(verify_path),
            )
        )
    return results


def _check_execute_workflow(execute_skill: Path) -> list[CheckResult]:
    """Check R30, R32, and R33 in prothon-execute skill."""
    results = []
    req_map = {
        "R30": "Each task must execute in an isolated agent context.",
        "R32": "System must run pre-commit hooks after each task.",
        "R33": "System must retry failed tasks up to max attempts.",
    }
    if not execute_skill.exists():
        return results

    content = execute_skill.read_text()
    if "fresh-context subagent loops" in content or "Fresh instances" in content:
        results.append(
            CheckResult(
                Requirement("SPEC", req_map["R30"], "R30"),
                CheckStatus.PASS,
                evidence=str(execute_skill),
            )
        )
    if "pre-commit" in content:
        results.append(
            CheckResult(
                Requirement("SPEC", req_map["R32"], "R32"),
                CheckStatus.PASS,
                evidence=str(execute_skill),
            )
        )
    if "record-attempt" in content or "retries" in content:
        results.append(
            CheckResult(
                Requirement("SPEC", req_map["R33"], "R33"),
                CheckStatus.PASS,
                evidence=str(execute_skill),
            )
        )
    return results


def check_refactor_logic(root: Path) -> list[CheckResult]:
    """Verify Refactor workflow implementation (SPEC R38-R42)."""
    results = []
    req_map = {
        "R38": "System must provide refactor workflow via CLI.",
        "R39": "Refactor Wave: DESIGN -> PATTERNS -> CODE.",
        "R40": "Discovery phase scanning for doc-code drift.",
        "R41": "Execution phase using self-correcting subagent loops.",
        "R42": "Refactor tasks must reference documentation headings.",
    }

    refactor_path = root / "src" / "prothon" / "refactor.py"
    refactor_skill = (
        root / "src" / "prothon" / "skills" / "prothon-refactor" / "SKILL.md"
    )

    # R38: refactor.py existence
    if refactor_path.exists():
        results.append(
            CheckResult(
                Requirement("SPEC", req_map["R38"], "R38"),
                CheckStatus.PASS,
                evidence=str(refactor_path),
            )
        )

    if refactor_skill.exists():
        content = refactor_skill.read_text()
        # R39: Refactor Wave
        if "DESIGN -> PATTERNS -> CODE" in content:
            results.append(
                CheckResult(
                    Requirement("SPEC", req_map["R39"], "R39"),
                    CheckStatus.PASS,
                    evidence=str(refactor_skill),
                )
            )
        # R40: Discovery phase
        if "Phase 1: Interactive Discovery" in content:
            results.append(
                CheckResult(
                    Requirement("SPEC", req_map["R40"], "R40"),
                    CheckStatus.PASS,
                    evidence=str(refactor_skill),
                )
            )
        # R41: Execution phase
        if "Phase 2: Execution" in content and "subagent" in content:
            results.append(
                CheckResult(
                    Requirement("SPEC", req_map["R41"], "R41"),
                    CheckStatus.PASS,
                    evidence=str(refactor_skill),
                )
            )
        # R42: Task documentation reference
        if "reference the specific documentation heading" in content:
            results.append(
                CheckResult(
                    Requirement("SPEC", req_map["R42"], "R42"),
                    CheckStatus.PASS,
                    evidence=str(refactor_skill),
                )
            )

    return results


def _check_tech_researcher_skill_existence(root: Path, r43: Requirement) -> CheckResult:
    skill_path = (
        root / "src" / "prothon" / "skills" / "prothon-tech-researcher" / "SKILL.md"
    )
    if skill_path.exists():
        return CheckResult(
            requirement=r43, status=CheckStatus.PASS, evidence=str(skill_path)
        )
    return CheckResult(
        requirement=r43,
        status=CheckStatus.FAIL,
        evidence=str(skill_path),
        rationale="Missing prothon-tech-researcher skill.",
    )


def _has_tech_choices(design_path: Path) -> bool:
    if design_path.exists():
        content = design_path.read_text()
        if "Technology Choices" in content or "Key Decisions" in content:
            return True
    return False


def _verify_skill_folders(
    skill_folders: list[Path], skills_dir: Path, r45: Requirement
) -> list[CheckResult]:
    kebab_pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    violations = []

    for folder in skill_folders:
        if not kebab_pattern.match(folder.name):
            violations.append(f"Folder '{folder.name}' is not kebab-case.")
        if not (folder / "SKILL.md").exists():
            violations.append(f"Folder '{folder.name}' is missing SKILL.md.")

    if violations:
        return [
            CheckResult(
                requirement=r45,
                status=CheckStatus.FAIL,
                evidence=str(skills_dir),
                rationale="; ".join(violations),
            )
        ]
    return [
        CheckResult(requirement=r45, status=CheckStatus.PASS, evidence=str(skills_dir))
    ]


def _check_reference_skills_storage(root: Path, r45: Requirement) -> list[CheckResult]:
    design_path = root / "docs" / "DESIGN.md"
    skills_dir = root / ".agents" / "skills"
    has_tech = _has_tech_choices(design_path)

    if not skills_dir.exists():
        if has_tech:
            return [
                CheckResult(
                    requirement=r45,
                    status=CheckStatus.FAIL,
                    evidence=str(skills_dir),
                    rationale="DESIGN.md has technology choices but .agents/skills/ is missing.",
                )
            ]
        return [
            CheckResult(
                requirement=r45,
                status=CheckStatus.SKIP,
                rationale="No technology choices in DESIGN.md and .agents/skills/ missing.",
            )
        ]

    # Check skills directory content
    skill_folders = [d for d in skills_dir.iterdir() if d.is_dir()]
    if not skill_folders:
        if has_tech:
            return [
                CheckResult(
                    requirement=r45,
                    status=CheckStatus.FAIL,
                    evidence=str(skills_dir),
                    rationale="DESIGN.md has technology choices but .agents/skills/ is empty.",
                )
            ]
        return [
            CheckResult(
                requirement=r45,
                status=CheckStatus.PASS,
                evidence=str(skills_dir),
                rationale=".agents/skills/ exists and is empty (no tech choices expected).",
            )
        ]

    return _verify_skill_folders(skill_folders, skills_dir, r45)


def check_tech_researcher(root: Path) -> list[CheckResult]:
    """Verify Tech-Researcher implementation (SPEC R43-R46)."""
    results = []
    r43 = Requirement(
        source="SPEC",
        requirement_id="R43",
        statement="System must automatically generate reference skills based on technology choices.",
    )
    r45 = Requirement(
        source="SPEC",
        requirement_id="R45",
        statement="Reference skills must be stored in .agents/skills/ using kebab-case and SKILL.md.",
    )

    results.append(_check_tech_researcher_skill_existence(root, r43))
    results.extend(_check_reference_skills_storage(root, r45))

    return results
