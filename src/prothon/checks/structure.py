from __future__ import annotations

from pathlib import Path

from prothon.checks.utils import analyze_python_file, check_path_exists
from prothon.compliance import (
    CheckResult,
    CheckStatus,
    Requirement,
)


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
    req = Requirement(
        source="SPEC",
        requirement_id="R5",
        statement="Project must include pre-commit hooks configuration.",
    )
    return [
        check_path_exists(
            root,
            ".pre-commit-config.yaml",
            req,
            fail_rationale="Missing pre-commit config.",
        )
    ]


def check_skills_dir(root: Path) -> list[CheckResult]:
    """Verify project-specific skills directory existence (SPEC R15)."""
    req = Requirement(
        source="SPEC",
        requirement_id="R15",
        statement="Project must have a .agents/skills/ directory for project-specific reference skills.",
    )
    return [
        check_path_exists(
            root,
            ".agents/skills",
            req,
            is_dir=True,
            fail_rationale="Missing project skills directory.",
        )
    ]


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


def check_inheritance(root: Path) -> list[CheckResult]:
    """Verify all custom exceptions inherit from ProthonError."""
    results = []
    exc_path = root / "src" / "prothon" / "exceptions.py"
    if not exc_path.is_file():
        return results

    req = Requirement(
        source="DESIGN",
        statement="All domain exceptions must inherit from ProthonError.",
        requirement_id="D1",
    )
    analysis = analyze_python_file(exc_path)
    base_classes = analysis.get("base_classes", {})

    # Build transitive set of classes inheriting from ProthonError
    inheritors: set[str] = {"ProthonError"}
    changed = True
    while changed:
        changed = False
        for name, bases in base_classes.items():
            if name not in inheritors and inheritors & set(bases):
                inheritors.add(name)
                changed = True

    violations = [
        name
        for name, bases in base_classes.items()
        if name != "ProthonError" and name not in inheritors and bases
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
