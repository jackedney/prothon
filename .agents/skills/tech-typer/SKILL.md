---
name: tech-typer
description: Reference guide for Typer — CLI framework with type-hint-driven parameter inference
user-invocable: false
---

# Typer

> Purpose: CLI framework with type-hint-driven parameter inference (R32: CLI-invocable workflows)
> Docs: https://typer.tiangolo.com/
> Version researched: >=0.15 (latest 0.24.0, Feb 2026)

## Quick Start

```python
import typer

app = typer.Typer()

@app.command()
def hello(name: str):
    typer.echo(f"Hello {name}")

if __name__ == "__main__":
    app()
```

Typer reads function signatures — type hints become CLI parameters, defaults become optional flags, docstrings become help text.

## Common Patterns

### Multiple commands on one app

```python
app = typer.Typer()

@app.command()
def create(name: str):
    ...

@app.command()
def delete(name: str, force: bool = False):
    ...
```

### Subcommand groups with add_typer

```python
# promise.py
promise_app = typer.Typer()

@promise_app.command()
def plan():
    ...

@promise_app.command()
def status():
    ...

# cli.py
app = typer.Typer()
app.add_typer(promise_app, name="promise")
# Usage: prothon promise plan
```

### Options vs arguments

```python
@app.command()
def check(
    task_index: int,                                    # positional argument
    verbose: bool = typer.Option(False, "--verbose"),    # explicit option
    retries: int = typer.Option(3, help="Max retries"), # option with help
):
    ...
```

### Prompting for input

```python
@app.command()
def new():
    name = typer.prompt("Module name")
    desc = typer.prompt("Description", default="")
```

### Callbacks for app-level options

```python
@app.callback()
def main(verbose: bool = False):
    """Prothon CLI — documentation-driven development."""
    if verbose:
        state["verbose"] = True
```

## Gotchas & Pitfalls

- **Boolean flags generate `--flag/--no-flag` pairs by default.** If you only want `--flag`, use `typer.Option(False, "--flag", is_flag=True)` or annotate with `Annotated[bool, typer.Option("--flag")]`.
- **`typer.echo()` is still valid** but the docs recommend `print()` for simple output and Rich for styled output, since Rich is always available via the Typer dependency.
- **Typer wraps Click internally.** If you hit a Typer limitation, you can drop down to `click.get_current_context()` or access the underlying Click objects. But avoid mixing Typer decorators with raw Click decorators on the same function.
- **Testing: use `typer.testing.CliRunner`**, not Click's runner directly. The Typer runner handles Rich output and Typer-specific context properly.
- **Exit codes:** Raise `typer.Exit(code=1)` for non-zero exits. Unhandled exceptions produce code 1 automatically but with a traceback.
- **`add_typer()` name parameter is required** for the subcommand group name. Without it, Typer infers from the module name, which is fragile.

## Idiomatic Usage

**Do:** Keep command functions thin — call domain functions and format output.
```python
@app.command()
def compliance():
    report = compliance_mod.check(project.find_project_root())
    render_compliance_table(report)
```

**Don't:** Put business logic in command functions. They should be adapters between CLI input and domain code.

**Do:** Use `Annotated` for complex parameter metadata (Python 3.9+).
```python
from typing import Annotated

@app.command()
def check(
    task: Annotated[int, typer.Argument(help="Task index to verify")],
):
    ...
```

**Don't:** Use `typer.Argument()` as a default value — the `Annotated` form is preferred in modern Typer.

**Do:** Use `rich_help_panel` to organize `--help` output into sections for complex commands.
