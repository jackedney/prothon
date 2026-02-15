# uvx CLI Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `uvx perfect-python my-project` work as a standalone project generator with interactive prompts, Jinja2 templating, and no copier runtime dependency.

**Architecture:** A typer CLI that walks `template/`, renders `.jinja` files with Jinja2, copies plain files, creates symlinks, writes `.copier-answers.yml`, and runs `git init`. Template files are bundled into the wheel via hatchling `force-include`.

**Tech Stack:** typer (CLI), Jinja2 (templating), hatchling (packaging)

---

### Task 1: Create pyproject.toml for the CLI package

**Files:**
- Create: `pyproject.toml`

**Step 1: Create the file**

```toml
[project]
name = "perfect-python"
version = "0.1.0"
description = "Copier template for Python projects with docs-first AI workflow"
requires-python = ">=3.11"
license = "MIT"
dependencies = [
    "typer>=0.15",
    "jinja2>=3.1",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/perfect_python"]

[tool.hatch.build.targets.wheel.force-include]
"template" = "perfect_python/template"

[project.scripts]
perfect-python = "perfect_python.cli:app"
```

**Step 2: Verify**

Run: `cat pyproject.toml`
Expected: Shows the content above

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add pyproject.toml for CLI package"
```

---

### Task 2: Create package init

**Files:**
- Create: `src/perfect_python/__init__.py`

**Step 1: Create the directory and file**

```bash
mkdir -p src/perfect_python
```

```python
"""Perfect Python — project generator with docs-first AI workflow."""
```

**Step 2: Commit**

```bash
git add src/perfect_python/__init__.py
git commit -m "feat: add perfect_python package init"
```

---

### Task 3: Write tests for the generation logic

**Files:**
- Create: `tests/test_generate.py`

**Step 1: Create tests directory and file**

```bash
mkdir -p tests
```

Write the test file. These tests verify the core generation logic: Jinja2 rendering, path templating, file copying, symlink creation, and .copier-answers.yml generation.

```python
"""Tests for project generation."""

import os
from pathlib import Path

import pytest

from perfect_python.cli import generate


@pytest.fixture
def context():
    return {
        "project_name": "test-project",
        "module_name": "test_project",
        "description": "A test project",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "python_version": "3.13",
        "license": "MIT",
    }


@pytest.fixture
def generated_project(tmp_path, context):
    dest = tmp_path / "test-project"
    generate(dest, context)
    return dest


def test_creates_destination_directory(generated_project):
    assert generated_project.is_dir()


def test_renders_jinja_templates(generated_project):
    pyproject = generated_project / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text()
    assert 'name = "test-project"' in content
    assert "{{ project_name }}" not in content


def test_strips_jinja_suffix(generated_project):
    assert (generated_project / "pyproject.toml").exists()
    assert not (generated_project / "pyproject.toml.jinja").exists()


def test_copies_plain_files(generated_project):
    assert (generated_project / "Taskfile.yml").exists()
    assert (generated_project / ".gitignore").exists()


def test_templates_directory_paths(generated_project):
    init = generated_project / "src" / "test_project" / "__init__.py"
    assert init.exists()
    assert '"A test project"' in init.read_text()


def test_creates_symlinks(generated_project):
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = generated_project / name
        assert link.is_symlink()
        assert os.readlink(str(link)) == "AGENTS.md"


def test_writes_copier_answers(generated_project):
    answers = generated_project / ".copier-answers.yml"
    assert answers.exists()
    content = answers.read_text()
    assert "project_name: test-project" in content
    assert "module_name: test_project" in content


def test_creates_doc_scaffolds(generated_project):
    for name in ("SPEC.md", "DESIGN.md", "PATTERNS.md"):
        doc = generated_project / "docs" / name
        assert doc.exists()
        assert doc.stat().st_size > 0


def test_creates_skill_files(generated_project):
    skills_dir = generated_project / "docs" / "skills"
    expected = [
        "spec-writer.md",
        "design-writer.md",
        "tech-researcher.md",
        "patterns-writer.md",
        "doc-harmonizer.md",
        "compliance-checker.md",
    ]
    for name in expected:
        assert (skills_dir / name).exists()


def test_creates_agents_md(generated_project):
    agents = generated_project / "AGENTS.md"
    assert agents.exists()
    content = agents.read_text()
    assert "# test-project" in content
    assert "A test project" in content


def test_skips_copier_answers_template(generated_project):
    # The copier-specific answers template should not be rendered
    assert not (generated_project / "{{ _copier_conf.answers_file }}").exists()


def test_git_initialized(generated_project):
    assert (generated_project / ".git").is_dir()


def test_license_none_excluded(tmp_path):
    context = {
        "project_name": "no-license",
        "module_name": "no_license",
        "description": "No license project",
        "author_name": "Test",
        "author_email": "test@example.com",
        "python_version": "3.13",
        "license": "None",
    }
    dest = tmp_path / "no-license"
    generate(dest, context)
    content = (dest / "pyproject.toml").read_text()
    assert "license" not in content.lower() or 'license = "None"' not in content
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generate.py -v`
Expected: FAIL — `generate` function doesn't exist yet

**Step 3: Commit**

```bash
git add tests/test_generate.py
git commit -m "test: add generation logic tests"
```

---

### Task 4: Implement the CLI and generation logic

**Files:**
- Create: `src/perfect_python/cli.py`

**Step 1: Write the implementation**

```python
"""Perfect Python CLI — project generator with docs-first AI workflow."""

import os
import shutil
import subprocess
from pathlib import Path

import typer
from jinja2 import Environment, BaseLoader

app = typer.Typer(add_completion=False)

COPIER_ANSWERS_TEMPLATE = "{{ _copier_conf.answers_file }}.jinja"


def _template_dir() -> Path:
    """Return the path to the bundled template directory."""
    return Path(__file__).parent / "template"


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

        # Skip the copier-specific answers template
        if COPIER_ANSWERS_TEMPLATE in str(rel_path):
            continue

        # Template the path itself (handles {{ module_name }} dirs)
        rendered_rel = env.from_string(str(rel_path)).render(context)
        dest_path = dest / rendered_rel

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.suffix == ".jinja":
            # Render Jinja template and strip .jinja suffix
            dest_path = dest_path.with_suffix("")
            content = src_path.read_text()
            rendered = env.from_string(content).render(context)
            dest_path.write_text(rendered)
        else:
            # Copy as-is
            shutil.copy2(src_path, dest_path)

    # Create symlinks
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = dest / name
        if not link.exists():
            os.symlink("AGENTS.md", link)

    # Write .copier-answers.yml for copier update support
    _write_copier_answers(dest, context)

    # Initialize git
    subprocess.run(["git", "init"], cwd=dest, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=dest, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit from perfect-python template"],
        cwd=dest,
        capture_output=True,
        check=True,
    )


def _write_copier_answers(dest: Path, context: dict) -> None:
    """Write .copier-answers.yml for copier update compatibility."""
    lines = [
        "# Changes here will be overwritten by Copier",
        "_src_path: gh:jackedney/perfect-python",
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


@app.command()
def main(
    destination: str = typer.Argument(help="Directory to create the project in"),
) -> None:
    """Generate a new Python project with docs-first AI workflow."""
    dest = Path(destination).resolve()

    if dest.exists() and any(dest.iterdir()):
        typer.echo(f"Error: {dest} already exists and is not empty", err=True)
        raise typer.Exit(1)

    project_name = dest.name

    module_name = typer.prompt(
        "Module name",
        default=project_name.lower().replace("-", "_").replace(" ", "_"),
    )
    description = typer.prompt("Description", default="A Python project")
    author_name = typer.prompt("Author name")
    author_email = typer.prompt("Author email")

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
    typer.echo("  task check")
```

**Step 2: Run tests**

Run: `uv sync && uv run pytest tests/test_generate.py -v`
Expected: Most tests PASS. Fix any failures.

**Step 3: Commit**

```bash
git add src/perfect_python/cli.py
git commit -m "feat: implement CLI with typer and Jinja2 generation"
```

---

### Task 5: Manual integration test

**Step 1: Test with uv run**

Run:
```bash
echo -e "test_project\nA test project\nTest Author\ntest@example.com\n3.13\nMIT" | \
  uv run perfect-python /tmp/test-manual
```

**Step 2: Verify output structure**

Run: `find /tmp/test-manual -maxdepth 3 -not -path '*/.git/*' | sort`

Expected: All template files present, no `.jinja` suffixes, `src/test_project/` directory, symlinks, AGENTS.md with rendered values.

**Step 3: Verify symlinks and content**

Run:
```bash
ls -la /tmp/test-manual/CLAUDE.md
head -3 /tmp/test-manual/AGENTS.md
grep "test-project" /tmp/test-manual/pyproject.toml
cat /tmp/test-manual/.copier-answers.yml
```

**Step 4: Clean up**

Run: `rm -rf /tmp/test-manual`

---

### Task 6: Test with uvx

**Step 1: Test local uvx install**

Run:
```bash
echo -e "test_project\nA test\nTest\ntest@test.com\n3.13\nMIT" | \
  uvx --from /home/jackedney/Dev/perfect-python perfect-python /tmp/test-uvx
```

**Step 2: Verify it works**

Run:
```bash
ls /tmp/test-uvx/CLAUDE.md && head -2 /tmp/test-uvx/AGENTS.md && echo "OK"
```

Expected: Shows symlink, shows `# test-uvx` / `A test`, prints OK.

**Step 3: Clean up**

Run: `rm -rf /tmp/test-uvx`

**Step 4: Commit any fixes**

If fixes were needed, commit them.

---

### Task 7: Update README

**Files:**
- Modify: `README.md`

**Step 1: Update Quick Start to use uvx**

Replace the current Quick Start section. The primary method should be `uvx perfect-python`, with copier as an alternative.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for uvx usage"
```
