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

### Per-command options with envvar fallback

Per DESIGN.md, `--agent` is a per-command option (not a global callback), defined on each session command via a shared `AgentOption` annotated type. `--model` and `--provider` follow the same pattern.

```python
from typing import Annotated

AgentOption = Annotated[
    str | None,
    typer.Option("--agent", "-a", envvar="PROTHON_AGENT", help="AI assistant backend"),
]

ModelOption = Annotated[
    str | None,
    typer.Option("--model", "-m", envvar="PROTHON_MODEL", help="Model name"),
]

ProviderOption = Annotated[
    str | None,
    typer.Option("--provider", "-p", envvar="PROTHON_PROVIDER", help="Model provider"),
]

@app.command()
def spec(
    agent: AgentOption = None,
    model: ModelOption = None,
    provider: ProviderOption = None,
):
    resolved = resolve_agent(agent)
    ...
```

Typer natively handles env var fallback via `envvar=`. Each session command (`spec`, `design`, `patterns`, `execute`, `compliance`) declares these options. Non-session commands (`new`, `init`, `promise *`) do not.

### Prompting for interactive input

```python
@app.command()
def new():
    name = typer.prompt("Module name")
    desc = typer.prompt("Description", default="")
    confirm = typer.confirm("Proceed?")
```

### Rich markup mode for help text

```python
app = typer.Typer(rich_markup_mode="rich")

@app.command()
def create(
    username: Annotated[str, typer.Argument(help="The username to create")],
    age: Annotated[
        int | None,
        typer.Option(help="User age", rich_help_panel="Additional Data"),
    ] = None,
):
    """[green]Create[/green] a new user."""
    print(f"Creating user: {username}")
```

Use `rich_help_panel` to organize `--help` output into sections.

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
- **`envvar=` on `typer.Option`** reads the env var automatically and uses it as a fallback when the CLI flag is not provided. This powers the 5-level precedence chain in DESIGN.md (levels 1-2).

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

**Do:** Use shared annotated types (`AgentOption`, `ModelOption`, `ProviderOption`) for per-command options that repeat across session commands.

**Do:** Use `typer.Context` parameter for accessing the invoked subcommand or parent context when needed.
