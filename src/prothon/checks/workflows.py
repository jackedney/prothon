from __future__ import annotations

from pathlib import Path

from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


def _check_marker(
    content: str,
    markers: list[str],
    req_id: str,
    statement: str,
    evidence: str,
    *,
    require_all: bool = False,
) -> CheckResult:
    """Return PASS if any (or all) markers are found in content, else FAIL."""
    check = all if require_all else any
    found = check(m in content for m in markers)
    status = CheckStatus.PASS if found else CheckStatus.FAIL
    rationale = "" if found else f"Missing marker for {req_id}."
    return CheckResult(
        Requirement("SPEC", statement, req_id),
        status,
        evidence=evidence,
        rationale=rationale,
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
    ev = str(promise_path)
    if not promise_path.exists():
        return [
            CheckResult(
                Requirement(
                    "SPEC",
                    "System must provide execute workflow generating a plan of tasks.",
                    "R27",
                ),
                CheckStatus.SKIP,
                evidence=ev,
                rationale="promise.py not found.",
            ),
            CheckResult(
                Requirement(
                    "SPEC", "Tasks must declare files to touch and line counts.", "R28"
                ),
                CheckStatus.SKIP,
                evidence=ev,
                rationale="promise.py not found.",
            ),
        ]

    content = promise_path.read_text()
    ev = str(promise_path)
    return [
        _check_marker(
            content,
            ["def plan"],
            "R27",
            "System must provide execute workflow generating a plan of tasks.",
            ev,
        ),
        _check_marker(
            content,
            ["expected_lines_added", "files_to_modify"],
            "R28",
            "Tasks must declare files to touch and line counts.",
            ev,
            require_all=True,
        ),
    ]


def _check_execute_verification(verify_path: Path) -> list[CheckResult]:
    """Check R31 in promise_verify.py."""
    if not verify_path.exists():
        return []

    content = verify_path.read_text()
    return [
        _check_marker(
            content,
            ["check_task", "actual_added"],
            "R31",
            "System must verify actual changes against declared plan.",
            str(verify_path),
            require_all=True,
        ),
    ]


def _check_execute_workflow(execute_skill: Path) -> list[CheckResult]:
    """Check R30, R32, and R33 in prothon-execute skill."""
    if not execute_skill.exists():
        return []

    content = execute_skill.read_text()
    ev = str(execute_skill)
    return [
        _check_marker(
            content,
            ["fresh-context subagent loops", "Fresh instances"],
            "R30",
            "Each task must execute in an isolated agent context.",
            ev,
        ),
        _check_marker(
            content,
            ["pre-commit"],
            "R32",
            "System must run pre-commit hooks after each task.",
            ev,
        ),
        _check_marker(
            content,
            ["record-attempt", "retries"],
            "R33",
            "System must retry failed tasks up to max attempts.",
            ev,
        ),
    ]


def check_refactor_logic(root: Path) -> list[CheckResult]:
    """Verify Refactor workflow implementation (SPEC R38-R42)."""
    results = []

    refactor_path = root / "src" / "prothon" / "refactor.py"
    refactor_skill = (
        root / "src" / "prothon" / "skills" / "prothon-refactor" / "SKILL.md"
    )

    # R38: refactor.py existence
    status = CheckStatus.PASS if refactor_path.exists() else CheckStatus.FAIL
    rationale = "" if refactor_path.exists() else "Missing refactor.py."
    results.append(
        CheckResult(
            Requirement(
                "SPEC", "System must provide refactor workflow via CLI.", "R38"
            ),
            status,
            evidence=str(refactor_path),
            rationale=rationale,
        )
    )

    if refactor_skill.exists():
        content = refactor_skill.read_text()
        ev = str(refactor_skill)
        results.extend(
            [
                _check_marker(
                    content,
                    ["DESIGN -> PATTERNS -> CODE"],
                    "R39",
                    "Refactor Wave: DESIGN -> PATTERNS -> CODE.",
                    ev,
                ),
                _check_marker(
                    content,
                    ["Phase 1: Interactive Discovery"],
                    "R40",
                    "Discovery phase scanning for doc-code drift.",
                    ev,
                ),
                _check_marker(
                    content,
                    ["Phase 2: Execution", "subagent"],
                    "R41",
                    "Execution phase using self-correcting subagent loops.",
                    ev,
                    require_all=True,
                ),
                _check_marker(
                    content,
                    ["reference the specific documentation heading"],
                    "R42",
                    "Refactor tasks must reference documentation headings.",
                    ev,
                ),
            ]
        )

    return results
