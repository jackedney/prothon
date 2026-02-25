---
name: tech-rich
description: Reference guide for Rich -- terminal table rendering and formatted output
user-invocable: false
---

# Rich

> Purpose: Table rendering for promise plans, status, and compliance reports (R33: compliance report with PASS/FAIL/SKIP status)
> Docs: https://rich.readthedocs.io/
> Version researched: 14.x (Feb 2026). Installed at zero marginal cost via Typer dependency.

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
table.add_row("R24: Compliance", "[red]FAIL[/red]", "---")

console.print(table)
```

## Common Patterns

### Tables with styled status columns

```python
table = Table(title="Promise Status", show_header=True, header_style="bold magenta")
table.add_column("Task", style="bold")
table.add_column("Status", justify="center")
table.add_column("Attempts", justify="right")

for task in tasks:
    status = "[green]DONE[/green]" if task.completed else "[yellow]PENDING[/yellow]"
    table.add_row(task.title, status, str(task.attempts))

console.print(table)
```

### Column styling and alignment

```python
table = Table(title="Star Wars Movies")
table.add_column("Released", justify="right", style="cyan", no_wrap=True)
table.add_column("Title", style="magenta")
table.add_column("Box Office", justify="right", style="green")
```

### Section separators and row styles

```python
# Horizontal line between groups
table.add_row("Task 1", "PASS", "file.py:10")
table.add_section()
table.add_row("Task 2", "FAIL", "---")

# Alternating row styles for readability
table = Table(row_styles=["", "dim"])
```

### Tables with footers

```python
table = Table(show_footer=True)
table.add_column("Product", footer="Total")
table.add_column("Revenue", justify="right", footer="$25,000")
table.add_row("Widget A", "$10,000")
table.add_row("Widget B", "$15,000")
```

### Box styles for different contexts

```python
from rich import box

table = Table(box=box.SIMPLE)                # minimal for dense output
table = Table(box=None)                      # no borders for piped output
table = Table(box=box.MINIMAL_DOUBLE_HEAD)   # double header line for reports
```

### Console.print for rich text outside tables

```python
console.print("[bold green]All checks passed.[/bold green]")
console.print("[bold red]3 failures found.[/bold red]")
console.print(f"  [dim]{file_path}:{line}[/dim]")
```

### Separate console for stderr

```python
console = Console()
err_console = Console(stderr=True)

err_console.print("[red]Error: file not found[/red]")
```

### Status spinners for indeterminate operations

```python
with console.status("[bold green]Working on tasks...") as status:
    for task in tasks:
        console.log(f"Starting {task}")
        process(task)
        console.log(f"[green]Completed {task}[/]")
        status.update(f"[bold green]Processing {next_task}...")
```

`console.log()` inside `console.status()` prints timestamped lines above the spinner.

### Progress bars for determinate operations

```python
from rich.progress import track

for item in track(range(100), description="Processing..."):
    process(item)
```

For custom progress bars with multiple columns:

```python
from rich.table import Column
from rich.progress import Progress, BarColumn, TextColumn

text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
bar_column = BarColumn(bar_width=None, table_column=Column(ratio=2))

with Progress(text_column, bar_column, expand=True) as progress:
    task = progress.add_task("Working...", total=100)
    for n in range(100):
        progress.update(task, advance=1)
```

## Gotchas & Pitfalls

- **Rich markup uses `[style]text[/style]` syntax.** Literal square brackets in dynamic data will be misinterpreted as markup. Escape with `rich.markup.escape()`, pass `markup=False` to `console.print()`, or use `Text(data)` which bypasses markup parsing. Note: `highlight=False` only disables syntax highlighting, not markup parsing.
- **To escape brackets in strings**, use `r"foo\[bar]"` with a raw string or `"foo\\[bar]"`.
- **`console.print()` auto-detects terminal width.** Tables wider than the terminal will be truncated or wrapped. Set `table.width` or `table.min_width` for predictable output.
- **`Table.add_row()` accepts `*renderables`, not keyword arguments.** Column values are positional, matching column add order. Passing fewer values than columns is allowed; passing more raises an error.
- **Rich is always available in Typer apps** -- import from `rich` directly, not from `typer.rich_utils`.
- **Empty tables still render headers.** Check for empty data before printing to avoid a header-only table with no rows.
- **`Table.grid()` produces layout-only tables** with no borders and no headers -- useful for aligned columns without table chrome.

## Idiomatic Usage

**Do:** Create a shared `Console` instance in your CLI module and pass it to rendering functions.

**Do:** Use Rich markup strings for status indicators.
```python
status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
```

**Don't:** Use `print()` alongside `console.print()` -- mixing them causes inconsistent output formatting.

**Don't:** Over-style output. Use color for status (PASS/FAIL/SKIP) and structure (headers, sections). Leave data content unstyled.

**Do:** Use `console.status()` for operations without predictable progress, `track()` for operations with known total.

**Do:** Use `console.log()` inside status context for timestamped progress messages that appear above the spinner.
