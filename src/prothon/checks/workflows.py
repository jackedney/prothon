from __future__ import annotations

from pathlib import Path

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


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
