# Workflow CLI Commands Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `spec`, `design`, `patterns`, and `compliance` subcommands to the prothon CLI that launch interactive Claude Code sessions with the appropriate skill loaded.

**Architecture:** Each subcommand finds the project root, reads the skill file, and shells out to `claude` with `--append-system-prompt` for the skill content. The `design` command chains a second `claude` session for tech-researcher after the first exits. Skill files are updated to handle existing docs. AGENTS.md is updated to make harmonizer an always-on gate.

**Tech Stack:** typer (CLI framework), subprocess (launching claude), shutil (which for claude detection)

---

### Task 1: Add project detection helper

**Files:**
- Modify: `src/prothon/cli.py`
- Create: `tests/test_workflow.py`

**Step 1: Write the failing test**

In `tests/test_workflow.py`:

```python
"""Tests for workflow CLI commands."""

import os
from pathlib import Path

import pytest

from prothon.cli import find_project_root


def test_find_project_root_from_project_dir(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("project_name: test")
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_from_subdirectory(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("project_name: test")
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) == tmp_path


def test_find_project_root_not_found(tmp_path):
    assert find_project_root(tmp_path) is None
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_workflow.py -v`
Expected: FAIL — `find_project_root` not defined

**Step 3: Write minimal implementation**

In `src/prothon/cli.py`, add after the `_template_dir` function:

```python
def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find a prothon project root."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".copier-answers.yml").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
```

**Step 4: Run test to verify it passes**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_workflow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/prothon/cli.py tests/test_workflow.py
git commit -m "feat: add project root detection helper"
```

---

### Task 2: Add claude launcher helper

**Files:**
- Modify: `src/prothon/cli.py`
- Modify: `tests/test_workflow.py`

**Step 1: Write the failing test**

Append to `tests/test_workflow.py`:

```python
import shutil
from unittest.mock import patch

from prothon.cli import launch_claude


def test_launch_claude_calls_subprocess(tmp_path):
    with patch("prothon.cli.subprocess.run") as mock_run:
        with patch("prothon.cli.shutil.which", return_value="/usr/bin/claude"):
            launch_claude("You are a spec writer.", tmp_path)
    mock_run.assert_called_once_with(
        ["claude", "--append-system-prompt", "You are a spec writer."],
        cwd=tmp_path,
    )


def test_launch_claude_raises_when_claude_not_found(tmp_path):
    with patch("prothon.cli.shutil.which", return_value=None):
        with pytest.raises(typer.Exit):
            launch_claude("prompt", tmp_path)
```

Add `import typer` to top if not already there (it's imported via `from prothon.cli import ...`).

**Step 2: Run test to verify it fails**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_workflow.py::test_launch_claude_calls_subprocess tests/test_workflow.py::test_launch_claude_raises_when_claude_not_found -v`
Expected: FAIL — `launch_claude` not defined

**Step 3: Write minimal implementation**

In `src/prothon/cli.py`, add after `find_project_root`:

```python
def launch_claude(system_prompt: str, cwd: Path) -> None:
    """Launch an interactive Claude Code session with the given system prompt."""
    if not shutil.which("claude"):
        typer.echo(
            "Error: Claude Code CLI not found.\n"
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        )
        raise typer.Exit(1)
    subprocess.run(
        ["claude", "--append-system-prompt", system_prompt],
        cwd=cwd,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_workflow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/prothon/cli.py tests/test_workflow.py
git commit -m "feat: add claude launcher helper"
```

---

### Task 3: Restructure CLI to use subcommands

**Files:**
- Modify: `src/prothon/cli.py`
- Modify: `tests/test_generate.py` (update import if needed)

**Step 1: Write the failing test**

Append to `tests/test_workflow.py`:

```python
from typer.testing import CliRunner
from prothon.cli import app

runner = CliRunner()


def test_new_command_shows_help():
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "Generate" in result.output


def test_spec_command_exists():
    result = runner.invoke(app, ["spec", "--help"])
    assert result.exit_code == 0


def test_design_command_exists():
    result = runner.invoke(app, ["design", "--help"])
    assert result.exit_code == 0


def test_patterns_command_exists():
    result = runner.invoke(app, ["patterns", "--help"])
    assert result.exit_code == 0


def test_compliance_command_exists():
    result = runner.invoke(app, ["compliance", "--help"])
    assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_workflow.py::test_new_command_shows_help -v`
Expected: FAIL — no `new` subcommand

**Step 3: Restructure the CLI**

Replace the current `@app.command()` / `def main(...)` with subcommands. The full new structure of `src/prothon/cli.py`:

```python
"""Prothon CLI — Python project generator with docs-first AI workflow."""

import os
import shutil
import subprocess
from pathlib import Path

import typer
from jinja2 import Environment, BaseLoader

app = typer.Typer(
    add_completion=False,
    help="Python project generator with docs-first AI workflow.",
    invoke_without_command=True,
)

COPIER_ANSWERS_TEMPLATE = "{{ _copier_conf.answers_file }}.jinja"


def _template_dir() -> Path:
    """Return the path to the bundled template directory."""
    pkg_template = Path(__file__).parent / "template"
    if pkg_template.is_dir():
        return pkg_template
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "template"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find a prothon project root."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".copier-answers.yml").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def launch_claude(system_prompt: str, cwd: Path) -> None:
    """Launch an interactive Claude Code session with the given system prompt."""
    if not shutil.which("claude"):
        typer.echo(
            "Error: Claude Code CLI not found.\n"
            "Install: https://docs.anthropic.com/en/docs/claude-code"
        )
        raise typer.Exit(1)
    subprocess.run(
        ["claude", "--append-system-prompt", system_prompt],
        cwd=cwd,
    )


def _require_project_root() -> Path:
    """Find the project root or exit with an error."""
    root = find_project_root()
    if root is None:
        typer.echo(
            "Error: Not inside a prothon-generated project.\n"
            "Generate one with: uvx prothon new my-project"
        )
        raise typer.Exit(1)
    return root


def _read_skill(root: Path, skill_name: str) -> str:
    """Read a skill file from the project."""
    skill_path = root / ".agents" / "skills" / skill_name / "SKILL.md"
    if not skill_path.exists():
        typer.echo(f"Error: Skill file not found: {skill_path}")
        raise typer.Exit(1)
    return skill_path.read_text()


# --- generate logic (unchanged) ---

def generate(dest: Path, context: dict) -> None:
    """Generate a project from the template."""
    env = Environment(
        loader=BaseLoader(),
        keep_trailing_newline=True,
    )

    template_dir = _template_dir()
    dest.mkdir(parents=True, exist_ok=True)

    for src_path in sorted(template_dir.rglob("*")):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(template_dir)

        if COPIER_ANSWERS_TEMPLATE in str(rel_path):
            continue

        rendered_rel = env.from_string(str(rel_path)).render(context)
        dest_path = dest / rendered_rel

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.suffix == ".jinja":
            dest_path = dest_path.with_suffix("")
            content = src_path.read_text()
            rendered = env.from_string(content).render(context)
            dest_path.write_text(rendered)
        else:
            shutil.copy2(src_path, dest_path)

    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = dest / name
        if not link.exists():
            os.symlink("AGENTS.md", link)

    for dir_name in (".claude", ".opencode"):
        parent = dest / dir_name
        parent.mkdir(parents=True, exist_ok=True)
        link = parent / "skills"
        if not link.exists():
            os.symlink(os.path.join("..", ".agents", "skills"), link)

    _write_copier_answers(dest, context)

    subprocess.run(["git", "init"], cwd=dest, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=dest, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit from prothon template"],
        cwd=dest,
        capture_output=True,
        check=True,
    )


def _write_copier_answers(dest: Path, context: dict) -> None:
    """Write .copier-answers.yml for copier update compatibility."""
    lines = [
        "# Changes here will be overwritten by Copier",
        "_src_path: gh:jackedney/prothon",
    ]
    for key in (
        "project_name",
        "module_name",
        "description",
        "author_name",
        "author_email",
        "python_version",
        "license",
    ):
        lines.append(f"{key}: {context[key]}")
    (dest / ".copier-answers.yml").write_text("\n".join(lines) + "\n")


# --- CLI commands ---


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    destination: str = typer.Argument(default=None, help="Directory to create the project in"),
) -> None:
    """Python project generator with docs-first AI workflow."""
    if ctx.invoked_subcommand is not None:
        return
    if destination is not None:
        ctx.invoke(new, destination=destination)
    else:
        # No subcommand and no destination — show help
        typer.echo(ctx.get_help())


@app.command()
def new(
    destination: str = typer.Argument(help="Directory to create the project in"),
) -> None:
    """Generate a new Python project with docs-first AI workflow."""
    dest = Path(destination).resolve()
    project_name = dest.name

    module_name = typer.prompt(
        "Module name",
        default=project_name.lower().replace("-", "_").replace(" ", "_"),
    )
    description = typer.prompt("Description", default="A Python project")
    author_name = typer.prompt("Author name", default="")
    author_email = typer.prompt("Author email", default="")
    while author_email and "@" not in author_email:
        typer.echo("Must be a valid email address (e.g. user@example.com)")
        author_email = typer.prompt("Author email", default="")

    python_version = typer.prompt(
        "Python version (3.11/3.12/3.13)", default="3.13"
    )
    while python_version not in ("3.11", "3.12", "3.13"):
        typer.echo("Must be 3.11, 3.12, or 3.13")
        python_version = typer.prompt(
            "Python version (3.11/3.12/3.13)", default="3.13"
        )

    license_choice = typer.prompt("License (MIT/Apache-2.0/None)", default="MIT")
    while license_choice not in ("MIT", "Apache-2.0", "None"):
        typer.echo("Must be MIT, Apache-2.0, or None")
        license_choice = typer.prompt(
            "License (MIT/Apache-2.0/None)", default="MIT"
        )

    context = {
        "project_name": project_name,
        "module_name": module_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "python_version": python_version,
        "license": license_choice,
    }

    generate(dest, context)
    typer.echo(f"\nProject created at {dest}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {dest.name}")
    typer.echo("  uv sync")
    typer.echo("  poe check")


@app.command()
def spec() -> None:
    """Write or revise SPEC.md — extract requirements through probing questions."""
    root = _require_project_root()
    skill = _read_skill(root, "spec-writer")
    launch_claude(skill, root)


@app.command()
def design() -> None:
    """Write or revise DESIGN.md — research technologies and architecture, then generate tech references."""
    root = _require_project_root()
    skill = _read_skill(root, "design-writer")
    launch_claude(skill, root)
    # Chain tech-researcher after design session exits
    tech_skill = _read_skill(root, "tech-researcher")
    typer.echo("\nDesign complete. Launching tech-researcher to generate reference docs...\n")
    launch_claude(tech_skill, root)


@app.command()
def patterns() -> None:
    """Write or revise PATTERNS.md — define code conventions and testing approaches."""
    root = _require_project_root()
    skill = _read_skill(root, "patterns-writer")
    launch_claude(skill, root)


@app.command()
def compliance() -> None:
    """Verify source code matches documentation (SPEC.md, DESIGN.md, PATTERNS.md)."""
    root = _require_project_root()
    skill = _read_skill(root, "compliance-checker")
    launch_claude(skill, root)
```

**Step 4: Run all tests to verify nothing breaks**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/ -v`
Expected: All existing tests PASS + new tests PASS

Note: The existing `test_generate.py` tests import `generate` directly, so they are unaffected by the CLI restructure. If the `CliRunner` tests for `new` fail because typer prompts for input, the `--help` tests should still pass since they don't trigger prompts.

**Step 5: Commit**

```bash
git add src/prothon/cli.py tests/test_workflow.py
git commit -m "feat: restructure CLI with spec/design/patterns/compliance subcommands"
```

---

### Task 4: Add workflow command integration tests

**Files:**
- Modify: `tests/test_workflow.py`

**Step 1: Write tests for workflow commands requiring project context**

Append to `tests/test_workflow.py`:

```python
def test_spec_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["spec"])
    assert result.exit_code != 0
    assert "Not inside a prothon-generated project" in result.output


def test_design_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["design"])
    assert result.exit_code != 0
    assert "Not inside a prothon-generated project" in result.output


def test_spec_launches_claude_in_project(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.shutil.which", return_value="/usr/bin/claude"):
        with patch("prothon.cli.subprocess.run") as mock_run:
            result = runner.invoke(app, ["spec"])
    # subprocess.run is also called by generate (git init, etc.), so check the claude call
    claude_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "claude"]
    assert len(claude_calls) == 1
    assert "--append-system-prompt" in claude_calls[0].args[0]


def test_design_chains_tech_researcher(tmp_path, monkeypatch, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    monkeypatch.chdir(dest)
    with patch("prothon.cli.shutil.which", return_value="/usr/bin/claude"):
        with patch("prothon.cli.subprocess.run") as mock_run:
            result = runner.invoke(app, ["design"])
    claude_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "claude"]
    assert len(claude_calls) == 2  # design-writer + tech-researcher
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_workflow.py::test_spec_fails_outside_project tests/test_workflow.py::test_spec_launches_claude_in_project -v`
Expected: Tests should pass (if Task 3 implementation is correct) or fail (giving us feedback to fix).

**Step 3: Fix any issues from test results**

Adjust implementation as needed based on test feedback.

**Step 4: Run full test suite**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tests/test_workflow.py
git commit -m "test: add integration tests for workflow commands"
```

---

### Task 5: Update spec-writer skill for existing doc handling

**Files:**
- Modify: `template/.agents/skills/spec-writer/SKILL.md`

**Step 1: No test needed — this is a documentation/prompt change**

**Step 2: Add existing doc handling to the skill**

After the `## Process` heading, before step 1, add a new preliminary step. Replace the current `## Process` section with:

```markdown
## Process

0. **Check for existing SPEC.md** — Read `docs/SPEC.md`. If it exists and contains more than scaffold comments:
   - Present a summary of the current spec to the user
   - Ask: "Would you like to revise specific sections, add new requirements, or rewrite from scratch?"
   - Work through the requested changes section by section, preserving content the user doesn't want to change
   - Skip to step 3 for the sections being modified

1. **Explore context** — Read any existing code in `src/`, the README, and any prior docs. Understand what already exists.
2. **Ask clarifying questions** — One at a time. Start broad ("What problem does this solve?") and narrow down ("When you say 'fast', what response time is acceptable?"). Prefer multiple-choice questions when possible.
3. **Propose sections** — Once you understand the domain, draft each SPEC.md section and present it for approval:
   - Purpose (1-3 sentences, no jargon)
   - Requirements (numbered, testable statements)
   - Constraints (non-negotiable boundaries)
   - Out of Scope (explicit exclusions)
4. **Get approval** — Present each section individually. Revise based on feedback before moving on.
5. **Write SPEC.md** — Write the final approved content to `docs/SPEC.md`.
```

**Step 3: Commit**

```bash
git add template/.agents/skills/spec-writer/SKILL.md
git commit -m "feat: spec-writer handles existing SPEC.md for revisions"
```

---

### Task 6: Update design-writer skill for existing doc handling

**Files:**
- Modify: `template/.agents/skills/design-writer/SKILL.md`

**Step 1: Add existing doc handling**

Replace the current `## Process` section with:

```markdown
## Process

0. **Check for existing DESIGN.md** — Read `docs/DESIGN.md`. If it exists and contains more than scaffold comments:
   - Present a summary of the current design to the user
   - Ask: "Would you like to revise specific sections, update technology choices, or rewrite from scratch?"
   - Work through the requested changes section by section, preserving content the user doesn't want to change
   - Skip to step 4 for the sections being modified

1. **Read SPEC.md** — Understand every requirement and constraint thoroughly.
2. **Identify decisions** — List all technology/architecture decisions that need to be made to fulfill the SPEC.
3. **Research options** — For each decision, research 2-3 viable alternatives. Use web search and documentation to gather current information.
4. **Present trade-offs** — For each decision, present options with:
   - What it is and why it's a candidate
   - Pros and cons relative to the SPEC requirements
   - Your recommendation and why
5. **Get approval** — Present each DESIGN.md section individually. Revise based on feedback.
6. **Write DESIGN.md** — Write the final approved content to `docs/DESIGN.md`.
```

**Step 2: Commit**

```bash
git add template/.agents/skills/design-writer/SKILL.md
git commit -m "feat: design-writer handles existing DESIGN.md for revisions"
```

---

### Task 7: Update patterns-writer skill for existing doc handling

**Files:**
- Modify: `template/.agents/skills/patterns-writer/SKILL.md`

**Step 1: Add existing doc handling**

Replace the current `## Process` section with:

```markdown
## Process

0. **Check for existing PATTERNS.md** — Read `docs/PATTERNS.md`. If it exists and contains more than scaffold comments:
   - Present a summary of the current patterns to the user
   - Ask: "Would you like to revise specific patterns, add new conventions, or rewrite from scratch?"
   - Work through the requested changes section by section, preserving content the user doesn't want to change
   - Skip to step 3 for the sections being modified

1. **Read SPEC.md and DESIGN.md** — Understand requirements and technology choices.
2. **Analyze existing code** — If code exists in `src/`, study its current patterns.
3. **Propose patterns** — For each PATTERNS.md section, propose conventions with reasoning:
   - Code Organization: module structure, naming, layout
   - Design Patterns: which patterns apply and where
   - Error Handling: how errors flow through the system
   - Testing Patterns: test structure and conventions
4. **Show examples** — For each pattern, show a brief concrete example of what it looks like.
5. **Get approval** — Present each section individually. Revise based on feedback.
6. **Write PATTERNS.md** — Write the final approved content to `docs/PATTERNS.md`.
```

**Step 2: Commit**

```bash
git add template/.agents/skills/patterns-writer/SKILL.md
git commit -m "feat: patterns-writer handles existing PATTERNS.md for revisions"
```

---

### Task 8: Update AGENTS.md to make harmonizer an always-on gate

**Files:**
- Modify: `template/AGENTS.md.jinja`

**Step 1: Update the AGENTS.md template**

In the "Mandatory Development Workflow" section, replace step 4 (Harmonize) with an always-on instruction. Change:

```markdown
### 4. Harmonize

After any doc changes, invoke `/doc-harmonizer` to check for conflicts between doc levels.
```

To:

```markdown
### 4. Harmonize (Automatic)

**This is an always-on quality gate.** After making any changes to SPEC.md, DESIGN.md, or PATTERNS.md, you MUST automatically check for conflicts between doc levels before proceeding. Do not wait for the user to invoke `/doc-harmonizer` — perform the consistency check yourself:

- Verify DESIGN.md choices don't contradict SPEC.md requirements
- Verify PATTERNS.md conventions align with DESIGN.md technology choices
- If conflicts are found, flag them immediately and propose resolutions (higher-level doc always wins)
```

Also strengthen step 6 (Verify Compliance) to be always-on:

```markdown
### 6. Verify Compliance (Automatic)

**This is an always-on quality gate.** Before claiming any implementation work is complete, you MUST verify code matches documentation. Do not wait for the user to invoke `/compliance-checker` — check compliance yourself:

- Verify code implements SPEC.md requirements
- Verify code uses DESIGN.md technology choices
- Verify code follows PATTERNS.md conventions
- Report any deviations before marking work as done

For explicit full compliance scans, the user can run `uvx prothon compliance`.
```

**Step 2: Run generation test to verify AGENTS.md still renders**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/test_generate.py::test_creates_agents_md -v`
Expected: PASS

**Step 3: Commit**

```bash
git add template/AGENTS.md.jinja
git commit -m "feat: make harmonizer and compliance always-on quality gates in AGENTS.md"
```

---

### Task 9: Update next-steps output for new command

**Files:**
- Modify: `src/prothon/cli.py`

**Step 1: Update the `new` command's next-steps output**

Change the "Next steps" section at the end of the `new` command to mention the workflow commands:

```python
    typer.echo(f"\nProject created at {dest}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {dest.name}")
    typer.echo("  uv sync")
    typer.echo("  uvx prothon spec       # Write requirements")
    typer.echo("  uvx prothon design     # Choose architecture")
    typer.echo("  uvx prothon patterns   # Define conventions")
```

**Step 2: Run full test suite**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/prothon/cli.py
git commit -m "feat: update next-steps output to show workflow commands"
```

---

### Task 10: Final validation

**Step 1: Run full test suite**

Run: `cd /home/jackedney/Dev/prothon && uv run pytest tests/ -v`
Expected: All PASS

**Step 2: Verify CLI help output**

Run: `cd /home/jackedney/Dev/prothon && uv run prothon --help`
Expected: Shows `new`, `spec`, `design`, `patterns`, `compliance` subcommands

**Step 3: Verify generation still works**

Run: `cd /tmp && uvx --from /home/jackedney/Dev/prothon prothon new test-final`
Expected: Project generates successfully with prompts

**Step 4: Commit any final fixes**

```bash
git add -u
git commit -m "fix: final adjustments from validation"
```
