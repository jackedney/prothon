"""Rich-based terminal UI, tables, and status reporting."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from prothon.compliance import ComplianceReport
from prothon.models import Promise
from prothon.promise_verify import CheckStatus, TaskCheckReport

console = Console()


def render_plan(p: Promise) -> Table:
    """Build a Rich table for the promise plan."""
    base = p.metadata.base_commit or "unknown"
    task_word = "task" if len(p.tasks) == 1 else "tasks"

    table = Table(
        title=f"PLAN: {len(p.tasks)} {task_word} (base: {base})",
        show_lines=True,
    )
    table.add_column("#", style="bold", width=3)
    table.add_column("Title", style="bold")
    table.add_column("Files", no_wrap=False)
    table.add_column("Lines", justify="right")
    table.add_column("Deps")

    for i, task in enumerate(p.tasks):
        files_parts: list[str] = []
        if task.files_to_create:
            escaped = ", ".join(escape(f) for f in task.files_to_create)
            files_parts.append(f"[green]+[/green] {escaped}")
        if task.files_to_modify:
            escaped = ", ".join(escape(f) for f in task.files_to_modify)
            files_parts.append(f"[yellow]~[/yellow] {escaped}")
        if task.files_to_remove:
            escaped = ", ".join(escape(f) for f in task.files_to_remove)
            files_parts.append(f"[red]-[/red] {escaped}")
        files_cell = "\n".join(files_parts) if files_parts else "-"

        lines_cell = f"+{task.expected_lines_added} / -{task.expected_lines_removed}"

        deps_cell = (
            ", ".join(str(d) for d in task.dependencies)
            if task.dependencies
            else "none"
        )

        table.add_row(str(i), escape(task.title), files_cell, lines_cell, deps_cell)

    return table


def render_status(p: Promise) -> Table:
    """Build a Rich table for task completion status."""
    done = sum(1 for t in p.tasks if t.completed)
    table = Table(title=f"Status: {done}/{len(p.tasks)} completed")
    table.add_column("#", style="bold", width=3)
    table.add_column("Status", width=6)
    table.add_column("Title")

    for i, task in enumerate(p.tasks):
        if task.completed:
            status_cell = Text("\u2713", style="green")
        else:
            status_cell = Text("\u2717", style="red")
        table.add_row(str(i), status_cell, escape(task.title))

    return table


def render_check_report(report: TaskCheckReport) -> Table:
    """Build a Rich table for a task verification report."""
    result_style = "green" if report.passed else "red"
    result_label = "PASS" if report.passed else "DISCREPANCY"

    title = (
        f'Task {report.task_index}: "{escape(report.title)}" \u2014 '
        f"[{result_style}]{result_label}[/{result_style}]"
    )
    table = Table(title=title)
    table.add_column("Check", style="bold")
    table.add_column("Result", width=6)
    table.add_column("Detail")

    _status_styles = {
        CheckStatus.PASSED: ("PASS", "green"),
        CheckStatus.FAILED: ("FAIL", "red"),
        CheckStatus.SKIPPED: ("SKIP", "yellow"),
    }
    for c in report.checks:
        label, style = _status_styles[c.status]
        table.add_row(c.name, Text(label, style=style), c.detail)

    return table


def render_compliance_report(report: ComplianceReport) -> Table:
    """Build a Rich table for a compliance report."""
    table = Table(title="COMPLIANCE REPORT", show_lines=True)
    table.add_column("Type", width=10)
    table.add_column("Source", style="bold", width=10)
    table.add_column("ID", width=5)
    table.add_column("Requirement")
    table.add_column("Status", width=6)
    table.add_column("Evidence", no_wrap=False)

    from prothon.compliance import CheckStatus as ComplianceStatus

    _status_styles = {
        ComplianceStatus.PASS: ("PASS", "green"),
        ComplianceStatus.FAIL: ("FAIL", "red"),
        ComplianceStatus.SKIP: ("SKIP", "yellow"),
    }

    for res in report.results:
        label, style = _status_styles[res.status]
        table.add_row(
            res.check_type.value,
            res.requirement.source,
            res.requirement.requirement_id or "-",
            escape(res.requirement.statement),
            Text(label, style=style),
            escape(res.evidence) if res.evidence else "-",
        )

    return table
