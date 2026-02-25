---
name: tech-typer
description: Reference guide for Typer -- CLI framework with type-hint-driven parameter inference
user-invocable: false
---

# Typer

> Purpose: CLI framework with type-hint-driven parameter inference (R40: CLI-invocable workflows)
> Docs: https://typer.tiangolo.com/
> Version researched: >=0.15 (latest 0.24.1, Feb 2026)

## Quick Start

```python
import typer

app = typer.Typer()

@app.command()
def hello(name: str):
    print(f"Hello {name}")

if __name__ == "__main__":
    app()
```

Typer reads function signatures -- type hints become CLI parameters, defaults become optional flags, docstrings become help text.

## Common Patterns

### Multiple commands on one app

```python
app = typer.Typer()

@app.command()
def create(username: str):
    print(f"Creating user: {username}")

@app.command()
def delete(username: str, force: bool = False):
    if force:
        print(f"Deleting user: {username}")
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

### Options vs arguments with Annotated (modern style)

```python
from typing import Annotated

@app.command()
def check(
    task: Annotated[int, typer.Argument(help="Task index to verify")],
    verbose: Annotated[bool, typer.Option("--verbose", help="Verbose output")] = False,
    retries: Annotated[int, typer.Option(help="Max retries")] = 3,
):
    ...
```

### Prompting for interactive input

```python
@app.command()
def new():
    name = typer.prompt("Module name")
    desc = typer.prompt("Description", default="")
    confirm = typer.confirm("Proceed?")
```

### Callbacks for app-level (global) options

```python
state = {"verbose": False, "assistant": None}

@app.callback()
def main(
    assistant: Annotated[
        str | None,
        typer.Option("--assistant", "-a", envvar="PROTHON_ASSISTANT", help="AI assistant backend"),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
):
    """Prothon CLI -- documentation-driven development."""
    if assistant:
        state["assistant"] = assistant
    if verbose:
        state["verbose"] = True
```

Global options on `@app.callback()` apply to all subcommands. Typer natively handles env var fallback via `envvar=`.

### Rich markup mode for help text

```python
app = typer.Typer(rich_markup_mode="rich")

@app.command()
def create(
    username: Annotated[str, typer.Argument(help="The username to create")],
    lastname: Annotated[
        str,
        typer.Argument(help="The last name", rich_help_panel="Secondary Arguments"),
    ] = "",
    age: Annotated[
        int | None,
        typer.Option(help="User age", rich_help_panel="Additional Data"),
    ] = None,
):
    """[green]Create[/green] a new user."""
    print(f"Creating user: {username}")
```

Use `rich_help_panel` to organize `--help` output into sections. Use `rich_markup_mode="rich"` on the app for Rich markup in docstrings, or `rich_markup_mode="markdown"` for Markdown.

### Testing with CliRunner

```python
from typer.testing import CliRunner
from myapp.cli import app

runner = CliRunner()

def test_app():
    result = runner.invoke(app, ["Camila", "--city", "Berlin"])
    assert result.exit_code == 0
    assert "Hello Camila" in result.output
```

## Gotchas & Pitfalls

- **Boolean flags generate `--flag/--no-flag` pairs by default.** To get only `--flag`, use `Annotated[bool, typer.Option("--flag")]`.
- **`typer.echo()` is deprecated in favor of `print()`.** For styled output, use Rich directly (always available via Typer dependency).
- **Typer wraps Click internally.** You can access `click.get_current_context()` for advanced use, but avoid mixing Typer decorators with raw Click decorators on the same function.
- **Testing: use `typer.testing.CliRunner`**, not Click's runner directly. The Typer runner handles Rich output properly.
- **Exit codes:** Raise `typer.Exit(code=1)` for non-zero exits. Unhandled exceptions produce code 1 with traceback.
- **`add_typer()` name parameter is required.** Without it, Typer infers from the module name, which is fragile.
- **Rich markup in help strings.** Typer renders help strings with Rich, so literal square brackets in help text will be interpreted as markup. Use `\[` to escape.
- **Option with `prompt=True` and `confirmation_prompt=True`** can be used for sensitive inputs like emails that need double-entry verification.

## Idiomatic Usage

**Do:** Keep command functions thin -- call domain functions and format output.
```python
@app.command()
def compliance():
    report = compliance_mod.check(project.find_project_root())
    render_compliance_table(report)
```

**Don't:** Put business logic in command functions. They should be adapters between CLI input and domain code.

**Do:** Use `Annotated` for parameter metadata (preferred over positional defaults since Typer 0.9+).

**Don't:** Use `typer.Argument()` as a default value -- the `Annotated` form is the modern convention.

**Do:** Use `rich_help_panel` to organize `--help` output into sections for commands with many options.

**Do:** Use `typer.Context` parameter for accessing the invoked subcommand or parent context when needed.
