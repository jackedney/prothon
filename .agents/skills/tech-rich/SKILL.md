---
name: tech-rich
description: Reference guide for Rich — terminal table rendering and formatted output
user-invocable: false
---

# Rich

> Purpose: Table rendering for promise plans, status, and compliance reports (R25: compliance report with PASS/FAIL status)
> Docs: https://rich.readthedocs.io/
> Version researched: 14.1.0 (Feb 2026). Installed at zero marginal cost via Typer dependency.

## Quick Start

```python
from rich.console import Console
from rich.table import Table

console = Console()

table = Table(title="Compliance Report")
table.add_column("Requirement", style="cyan")
table.add_column("Status", justify="center")
table.add_column("Evidence")

table.add_row("R1: Scaffold", "[green]PASS[/green]", "src/scaffold.py:1")
table.add_row("R24: Compliance", "[red]FAIL[/red]", "—")

console.print(table)
```

## Common Patterns

### Tables with styled status columns

```python
table = Table(title="Promise Status")
table.add_column("Task", style="bold")
table.add_column("Status", justify="center")
table.add_column("Attempts", justify="right")

for task in tasks:
    status = "[green]DONE[/green]" if task.completed else "[yellow]PENDING[/yellow]"
    table.add_row(task.title, status, str(task.attempts))

console.print(table)
```

### Section separators

```python
table.add_row("Task 1", "PASS", "file.py:10")
table.add_section()  # horizontal line between groups
table.add_row("Task 2", "FAIL", "—")
```

### Alternating row styles

```python
table = Table(row_styles=["", "dim"])  # every other row is dimmed
```

### Box styles for different contexts

```python
from rich import box

# Minimal for dense output
table = Table(box=box.SIMPLE)

# No borders for piped output
table = Table(box=None)

# Double header line for reports
table = Table(box=box.MINIMAL_DOUBLE_HEAD)
```

### Console.print for rich text outside tables

```python
console.print("[bold green]All checks passed.[/bold green]")
console.print("[bold red]3 failures found.[/bold red]")
console.print(f"  [dim]{file_path}:{line}[/dim]")
```

## Gotchas & Pitfalls

- **Rich markup uses `[style]text[/style]` syntax.** Literal square brackets in data will be misinterpreted as markup. To prevent markup injection: use `rich.markup.escape()` on dynamic strings before embedding in f-strings, pass `markup=False` to `console.print()`, or use `Text(data)` which bypasses markup parsing. Note: `highlight=False` only disables syntax highlighting, not markup parsing.
- **`console.print()` auto-detects terminal width.** Tables wider than the terminal will be truncated or wrapped. Set `table.width` or `table.min_width` for predictable output.
- **`Table.add_row()` accepts `*renderables`, not keyword arguments.** Column values are positional, matching column add order. Passing fewer values than columns is allowed (empty cells); passing more raises an error.
- **Rich is always available in Typer apps** — no need to add it as a separate dependency. But import from `rich` directly, not from `typer.rich_utils`.
- **`Console(stderr=True)` for error output.** Use a separate console instance for errors to keep stdout clean for piped output.
- **Empty tables still render headers.** Check for empty data before printing to avoid a header-only table with no rows.

## Idiomatic Usage

**Do:** Create a shared `Console` instance in your CLI module and pass it to rendering functions.
```python
# cli.py
console = Console()
err_console = Console(stderr=True)
```

**Do:** Use Rich markup strings for status indicators rather than separate print statements.
```python
status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
```

**Don't:** Use `print()` alongside `console.print()` — mixing them causes inconsistent output formatting.

**Do:** Use `Table.grid()` for layout-only tables (no borders, no headers) when you need aligned columns without table chrome.

**Don't:** Over-style output. Use color for status indicators (PASS/FAIL/SKIP) and structure (headers, sections). Leave data content unstyled for readability.
