"""Tests for prothon.ui render functions."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from prothon.compliance import (
    CheckResult as ComplianceCheckResult,
    CheckStatus as ComplianceStatus,
    CheckType,
    ComplianceReport,
    Requirement,
)
from prothon.models import Metadata, Promise, Task
from prothon.promise_verify import CheckResult, CheckStatus, TaskCheckReport
from prothon.ui import (
    render_check_report,
    render_compliance_report,
    render_plan,
    render_status,
)


def _render_to_str(table: object) -> str:
    """Capture a Rich renderable to a plain-text string."""
    buf = StringIO()
    console = Console(file=buf, width=200, no_color=True)
    console.print(table)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers to build test data
# ---------------------------------------------------------------------------


def _make_task(**overrides: object) -> Task:
    defaults: dict = {
        "title": "test task",
        "task_id": "abc12345",
        "files_to_create": [],
        "files_to_modify": [],
        "files_to_remove": [],
        "expected_lines_added": 0,
        "expected_lines_removed": 0,
        "dependencies": [],
        "completed": False,
    }
    defaults.update(overrides)
    return Task(**defaults)


def _make_promise(
    tasks: list[Task] | None = None,
    base_commit: str = "abc1234",
) -> Promise:
    return Promise(
        metadata=Metadata(base_commit=base_commit),
        tasks=tasks or [],
    )


# ===================================================================
# render_plan
# ===================================================================


class TestRenderPlan:
    """Tests for render_plan."""

    def test_empty_tasks(self) -> None:
        p = _make_promise(tasks=[])
        table = render_plan(p)
        text = _render_to_str(table)
        assert "0 tasks" in text
        assert "abc1234" in text

    def test_single_task_singular_word(self) -> None:
        p = _make_promise(tasks=[_make_task(title="Do something")])
        table = render_plan(p)
        text = _render_to_str(table)
        assert "1 task" in text
        assert "1 tasks" not in text

    def test_multiple_tasks_plural_word(self) -> None:
        tasks = [_make_task(title="A"), _make_task(title="B")]
        p = _make_promise(tasks=tasks)
        table = render_plan(p)
        text = _render_to_str(table)
        assert "2 tasks" in text

    def test_column_headers(self) -> None:
        p = _make_promise(tasks=[_make_task()])
        text = _render_to_str(render_plan(p))
        for header in ("#", "Title", "Files", "Lines", "Deps"):
            assert header in text

    def test_files_create_modify_remove(self) -> None:
        task = _make_task(
            files_to_create=["new.py"],
            files_to_modify=["old.py"],
            files_to_remove=["dead.py"],
        )
        p = _make_promise(tasks=[task])
        text = _render_to_str(render_plan(p))
        assert "new.py" in text
        assert "old.py" in text
        assert "dead.py" in text

    def test_no_files_shows_dash(self) -> None:
        task = _make_task()
        p = _make_promise(tasks=[task])
        text = _render_to_str(render_plan(p))
        assert "-" in text

    def test_lines_display(self) -> None:
        task = _make_task(expected_lines_added=100, expected_lines_removed=20)
        p = _make_promise(tasks=[task])
        text = _render_to_str(render_plan(p))
        assert "+100" in text
        assert "-20" in text

    def test_dependencies_display(self) -> None:
        task = _make_task(dependencies=[0, 2])
        p = _make_promise(tasks=[task])
        text = _render_to_str(render_plan(p))
        assert "0" in text
        assert "2" in text

    def test_no_dependencies_shows_none(self) -> None:
        task = _make_task(dependencies=[])
        p = _make_promise(tasks=[task])
        text = _render_to_str(render_plan(p))
        assert "none" in text

    def test_unknown_base_commit(self) -> None:
        p = _make_promise(base_commit="")
        text = _render_to_str(render_plan(p))
        assert "unknown" in text


# ===================================================================
# render_status
# ===================================================================


class TestRenderStatus:
    """Tests for render_status."""

    def test_empty_tasks(self) -> None:
        p = _make_promise(tasks=[])
        text = _render_to_str(render_status(p))
        assert "0/0 completed" in text

    def test_all_completed(self) -> None:
        tasks = [
            _make_task(title="A", completed=True),
            _make_task(title="B", completed=True),
        ]
        p = _make_promise(tasks=tasks)
        text = _render_to_str(render_status(p))
        assert "2/2 completed" in text
        assert "\u2713" in text

    def test_none_completed(self) -> None:
        tasks = [
            _make_task(title="A", completed=False),
            _make_task(title="B", completed=False),
        ]
        p = _make_promise(tasks=tasks)
        text = _render_to_str(render_status(p))
        assert "0/2 completed" in text
        assert "\u2717" in text

    def test_mixed_status(self) -> None:
        tasks = [
            _make_task(title="Done", completed=True),
            _make_task(title="Pending", completed=False),
            _make_task(title="Also done", completed=True),
        ]
        p = _make_promise(tasks=tasks)
        text = _render_to_str(render_status(p))
        assert "2/3 completed" in text
        assert "Done" in text
        assert "Pending" in text

    def test_column_headers(self) -> None:
        p = _make_promise(tasks=[_make_task()])
        text = _render_to_str(render_status(p))
        for header in ("#", "Status", "Title"):
            assert header in text

    def test_task_title_in_output(self) -> None:
        p = _make_promise(tasks=[_make_task(title="My special task")])
        text = _render_to_str(render_status(p))
        assert "My special task" in text


# ===================================================================
# render_check_report
# ===================================================================


def _make_check(
    name: str = "files_to_create",
    status: CheckStatus = CheckStatus.PASSED,
    detail: str = "all good",
) -> CheckResult:
    return CheckResult(name=name, status=status, detail=detail)


class TestRenderCheckReport:
    """Tests for render_check_report."""

    def test_passing_report(self) -> None:
        report = TaskCheckReport(
            task_index=0,
            title="Create widget",
            task_id="abc",
            checks=[_make_check(status=CheckStatus.PASSED)],
        )
        text = _render_to_str(render_check_report(report))
        assert "PASS" in text
        assert "Create widget" in text

    def test_failing_report(self) -> None:
        report = TaskCheckReport(
            task_index=1,
            title="Broken task",
            task_id="def",
            checks=[_make_check(status=CheckStatus.FAILED, detail="missing file")],
        )
        text = _render_to_str(render_check_report(report))
        assert "DISCREPANCY" in text
        assert "FAIL" in text
        assert "missing file" in text

    def test_skipped_check(self) -> None:
        report = TaskCheckReport(
            task_index=0,
            title="Skip task",
            task_id="ghi",
            checks=[_make_check(status=CheckStatus.SKIPPED, detail="none declared")],
        )
        text = _render_to_str(render_check_report(report))
        assert "SKIP" in text
        assert "none declared" in text

    def test_mixed_checks(self) -> None:
        report = TaskCheckReport(
            task_index=2,
            title="Mixed",
            task_id="jkl",
            checks=[
                _make_check(name="files_to_create", status=CheckStatus.PASSED),
                _make_check(name="files_to_modify", status=CheckStatus.FAILED),
                _make_check(name="lines_added", status=CheckStatus.SKIPPED),
            ],
        )
        text = _render_to_str(render_check_report(report))
        # Overall should be DISCREPANCY because one check failed
        assert "DISCREPANCY" in text
        assert "files_to_create" in text
        assert "files_to_modify" in text
        assert "lines_added" in text

    def test_column_headers(self) -> None:
        report = TaskCheckReport(
            task_index=0, title="T", task_id="x", checks=[_make_check()]
        )
        text = _render_to_str(render_check_report(report))
        for header in ("Check", "Result", "Detail"):
            assert header in text

    def test_empty_checks(self) -> None:
        report = TaskCheckReport(task_index=0, title="Empty", task_id="y", checks=[])
        text = _render_to_str(render_check_report(report))
        # Should still render the title (PASS since no failures)
        assert "PASS" in text
        assert "Empty" in text

    def test_all_fail(self) -> None:
        report = TaskCheckReport(
            task_index=0,
            title="All bad",
            task_id="z",
            checks=[
                _make_check(name="a", status=CheckStatus.FAILED, detail="nope"),
                _make_check(name="b", status=CheckStatus.FAILED, detail="also nope"),
            ],
        )
        text = _render_to_str(render_check_report(report))
        assert "DISCREPANCY" in text
        assert text.count("FAIL") >= 2


# ===================================================================
# render_compliance_report
# ===================================================================


def _make_compliance_result(
    source: str = "SPEC",
    statement: str = "Must have tests",
    requirement_id: str | None = "R1",
    status: ComplianceStatus = ComplianceStatus.PASS,
    check_type: CheckType = CheckType.STATIC,
    evidence: str = "tests/test_foo.py:1",
) -> ComplianceCheckResult:
    req = Requirement(source=source, statement=statement, requirement_id=requirement_id)
    return ComplianceCheckResult(
        requirement=req,
        status=status,
        check_type=check_type,
        evidence=evidence,
    )


class TestRenderComplianceReport:
    """Tests for render_compliance_report."""

    def test_empty_report(self) -> None:
        report = ComplianceReport(results=[])
        text = _render_to_str(render_compliance_report(report))
        assert "COMPLIANCE REPORT" in text

    def test_column_headers(self) -> None:
        report = ComplianceReport(results=[_make_compliance_result()])
        text = _render_to_str(render_compliance_report(report))
        for header in ("Type", "Source", "ID", "Requirement", "Status", "Evidence"):
            assert header in text

    def test_all_pass(self) -> None:
        results = [
            _make_compliance_result(statement="Req A"),
            _make_compliance_result(statement="Req B"),
        ]
        report = ComplianceReport(results=results)
        text = _render_to_str(render_compliance_report(report))
        assert "PASS" in text
        assert "Req A" in text
        assert "Req B" in text

    def test_all_fail(self) -> None:
        results = [
            _make_compliance_result(statement="Bad A", status=ComplianceStatus.FAIL),
            _make_compliance_result(statement="Bad B", status=ComplianceStatus.FAIL),
        ]
        report = ComplianceReport(results=results)
        text = _render_to_str(render_compliance_report(report))
        assert text.count("FAIL") >= 2

    def test_mixed_status(self) -> None:
        results = [
            _make_compliance_result(statement="OK", status=ComplianceStatus.PASS),
            _make_compliance_result(statement="Bad", status=ComplianceStatus.FAIL),
            _make_compliance_result(statement="Skip", status=ComplianceStatus.SKIP),
        ]
        report = ComplianceReport(results=results)
        text = _render_to_str(render_compliance_report(report))
        assert "PASS" in text
        assert "FAIL" in text
        assert "SKIP" in text

    def test_check_type_displayed(self) -> None:
        results = [
            _make_compliance_result(check_type=CheckType.STATIC),
            _make_compliance_result(check_type=CheckType.SEMANTIC),
        ]
        report = ComplianceReport(results=results)
        text = _render_to_str(render_compliance_report(report))
        assert "STATIC" in text
        assert "SEMANTIC" in text

    def test_no_requirement_id_shows_dash(self) -> None:
        result = _make_compliance_result(requirement_id=None)
        report = ComplianceReport(results=[result])
        text = _render_to_str(render_compliance_report(report))
        assert "-" in text

    def test_no_evidence_shows_dash(self) -> None:
        result = _make_compliance_result(evidence="")
        report = ComplianceReport(results=[result])
        text = _render_to_str(render_compliance_report(report))
        # The rendered output should contain a dash for empty evidence
        assert "-" in text

    def test_source_and_id_displayed(self) -> None:
        result = _make_compliance_result(
            source="DESIGN", requirement_id="D5", statement="Architecture rule"
        )
        report = ComplianceReport(results=[result])
        text = _render_to_str(render_compliance_report(report))
        assert "DESIGN" in text
        assert "D5" in text
        assert "Architecture rule" in text
