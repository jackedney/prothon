"""Template rendering, copier answers, git init, project adoption."""

from __future__ import annotations

import os
from pathlib import Path

import tomlkit

from prothon.exceptions import GitError, ProjectAlreadyInitError
from prothon.git import run_git

_SPEC_SCAFFOLD = """\
# Project Specification

## Purpose

## Requirements

## Constraints

## Out of Scope
"""

_DESIGN_SCAFFOLD = """\
# Design Document

## Architecture

## Technology Choices

## Interfaces

## Key Decisions
"""

_PATTERNS_SCAFFOLD = """\
# Implementation Patterns

## Code Organization

## Design Patterns

## Error Handling

## Testing Patterns
"""

_VERSION_BUMP_WORKFLOW = """\
name: Version Bump

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize]

concurrency:
  group: version-bump-${{ github.head_ref }}
  cancel-in-progress: true

permissions:
  contents: write

jobs:
  version-bump:
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Check auto_version config
        id: config
        run: |
          AUTO_VERSION=$(python3 - <<'PYEOF'
          import sys
          try:
              import tomllib
          except ImportError:
              try:
                  import tomli as tomllib
              except ImportError:
                  print("true")
                  sys.exit(0)
          try:
              with open("pyproject.toml", "rb") as f:
                  data = tomllib.load(f)
              tool = data.get("tool", {})
              prothon = tool.get("prothon", {})
              ci = prothon.get("ci", {})
              val = ci.get("auto_version", True)
              print("true" if val else "false")
          except Exception:
              print("true")
          PYEOF
          )
          echo "auto_version=$AUTO_VERSION" >> "$GITHUB_OUTPUT"

      - name: Detect changed files and bump type
        if: steps.config.outputs.auto_version == 'true'
        id: detect
        run: |
          git fetch origin main
          BUMP_TYPE=$(python3 - <<'PYEOF'
          import subprocess
          import sys

          try:
              result = subprocess.run(
                  ["git", "diff", "--name-only", "origin/main...HEAD"],
                  capture_output=True,
                  text=True,
                  check=True,
              )
          except subprocess.CalledProcessError:
              print("none")
              sys.exit(0)

          files = {line.strip() for line in result.stdout.splitlines() if line.strip()}

          # Exclude version bump files from consideration
          files.discard("pyproject.toml")
          files = {f for f in files if not f.endswith("__init__.py")}

          if "docs/SPEC.md" in files:
              print("major")
          elif "docs/DESIGN.md" in files:
              print("minor")
          elif "docs/PATTERNS.md" in files or any(f.startswith("src/") for f in files):
              print("patch")
          else:
              print("none")
          PYEOF
          )
          echo "bump_type=$BUMP_TYPE" >> "$GITHUB_OUTPUT"

      - name: Apply version bump
        if: |
          steps.config.outputs.auto_version == 'true' &&
          steps.detect.outputs.bump_type != 'none'
        id: bump
        env:
          BUMP_TYPE: ${{ steps.detect.outputs.bump_type }}
        run: |
          pip install tomlkit
          python3 - <<'PYEOF'
          import io
          import os
          import re
          import subprocess
          import sys

          try:
              import tomllib
          except ImportError:
              try:
                  import tomli as tomllib
              except ImportError:
                  msg = (
                      "ERROR: tomllib not available "
                      "(Python < 3.11 and tomli not installed)"
                  )
                  print(msg, file=sys.stderr)
                  sys.exit(1)

          try:
              import tomlkit
          except ImportError:
              print("ERROR: tomlkit is required for version bumping", file=sys.stderr)
              sys.exit(1)

          bump_type = os.environ["BUMP_TYPE"]

          # Read current version from origin/main
          try:
              res = subprocess.run(
                  ["git", "show", "origin/main:pyproject.toml"],
                  capture_output=True,
                  check=True,
              )
              raw = tomllib.load(io.BytesIO(res.stdout))
          except Exception as e:
              msg = f"ERROR: failed to read pyproject.toml from origin/main: {e}"
              print(msg, file=sys.stderr)
              sys.exit(1)

          current = raw.get("project", {}).get("version", "")
          if not current:
              msg = "ERROR: no version found in pyproject.toml [project]"
              print(msg, file=sys.stderr)
              sys.exit(1)

          # Parse semver
          m = re.fullmatch(r"v?(\\d+)\\.(\\d+)\\.(\\d+)", current)
          if not m:
              print(f"ERROR: invalid version format: {current!r}", file=sys.stderr)
              sys.exit(1)
          major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))

          if bump_type == "major":
              new_version = f"{major + 1}.0.0"
          elif bump_type == "minor":
              new_version = f"{major}.{minor + 1}.0"
          else:
              new_version = f"{major}.{minor}.{patch + 1}"

          # Check if already bumped to this version
          with open("pyproject.toml", "rb") as f:
              branch_raw = tomllib.load(f)
          branch_version = branch_raw.get("project", {}).get("version", "")
          if branch_version == new_version:
              print(f"Version already at {new_version}, skipping")
              open(".bump_skipped", "w").write("true")
              sys.exit(0)

          print(f"Bumping {current} -> {new_version} ({bump_type})")

          # Update pyproject.toml using tomlkit to preserve formatting
          content = open("pyproject.toml", encoding="utf-8").read()
          doc = tomlkit.parse(content)
          doc["project"]["version"] = new_version
          open("pyproject.toml", "w", encoding="utf-8").write(tomlkit.dumps(doc))

          # Update src/<package>/__init__.py __version__
          import pathlib
          src_dir = pathlib.Path("src")
          init_files = list(src_dir.glob("*/__init__.py"))
          for init_path in init_files:
              text = init_path.read_text(encoding="utf-8")
              pattern = r'__version__\\s*=\\s*["\\'][^"\\']+["\\']'
              if re.search(pattern, text):
                  updated = re.sub(pattern, f'__version__ = "{new_version}"', text)
                  init_path.write_text(updated, encoding="utf-8")
                  print(f"Updated {init_path}")

          open(".new_version", "w").write(new_version)
          PYEOF

      - name: Commit and push version bump
        if: |
          steps.config.outputs.auto_version == 'true' &&
          steps.detect.outputs.bump_type != 'none'

        run: |
          if [ -f .bump_skipped ]; then
            echo "Version already bumped, nothing to do"
            rm -f .bump_skipped
            exit 0
          fi

          NEW_VERSION=$(cat .new_version)
          rm -f .new_version

          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          git add pyproject.toml
          git add src/

          # Only commit if there are staged changes
          if git diff --cached --quiet; then
            echo "No changes to commit"
            exit 0
          fi

          git commit -m "chore: bump version to ${NEW_VERSION}"
          git push
"""

_VERSION_TAG_WORKFLOW = """\
name: Version Tag

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  version-tag:
    if: "!startsWith(github.event.head_commit.message, 'chore: bump version')"
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Read version and create tag
        run: |
          VERSION=$(python3 - <<'PYEOF'
          import sys
          try:
              import tomllib
          except ImportError:
              try:
                  import tomli as tomllib
              except ImportError:
                  print("")
                  sys.exit(0)
          try:
              with open("pyproject.toml", "rb") as f:
                  data = tomllib.load(f)
              print(data.get("project", {}).get("version", ""))
          except Exception:
              print("")
          PYEOF
          )

          if [ -z "$VERSION" ]; then
            echo "No version found, skipping"
            exit 0
          fi

          TAG="v${VERSION}"

          # Check if tag already exists
          if git rev-parse "refs/tags/$TAG" >/dev/null 2>&1; then
            echo "Tag $TAG already exists, skipping"
            exit 0
          fi

          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          git tag -a "$TAG" -m "release ${VERSION}"
          git push origin "$TAG"
"""

_GITLAB_VERSION_BUMP = """\
stages:
  - version-bump

version-bump:
  stage: version-bump
  image: python:3.13
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  before_script:
    - pip install tomlkit
    - git config user.email "ci@gitlab"
    - git config user.name "GitLab CI"
  script:
    - |
      python - <<'PYEOF'
      import subprocess, sys, re, os
      from pathlib import Path

      # Read auto_version config
      try:
          import tomlkit
          doc = tomlkit.parse(Path("pyproject.toml").read_text())
          tool = doc.get("tool", {})
          prothon = tool.get("prothon", {})
          ci = prothon.get("ci", {})
          auto_version = ci.get("auto_version", True)
      except Exception:
          auto_version = True

      if not auto_version:
          print("auto_version is false — skipping version bump")
          sys.exit(0)

      # Detect changed files
      before_sha = os.environ.get("CI_COMMIT_BEFORE_SHA", "")
      current_sha = os.environ.get("CI_COMMIT_SHA", "HEAD")

      if not before_sha or before_sha == "0000000000000000000000000000000000000000":
          result = subprocess.run(
              ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
              capture_output=True, text=True
          )
      else:
          result = subprocess.run(
              ["git", "diff", "--name-only", before_sha, current_sha],
              capture_output=True, text=True
          )

      if result.returncode != 0:
          print(f"git diff failed: {result.stderr}", file=sys.stderr)
          sys.exit(1)

      files = {line for line in result.stdout.strip().splitlines() if line.strip()}
      print(f"Changed files: {files}")

      # Determine bump type
      if "docs/SPEC.md" in files:
          bump_type = "major"
      elif "docs/DESIGN.md" in files:
          bump_type = "minor"
      elif "docs/PATTERNS.md" in files or any(f.startswith("src/") for f in files):
          bump_type = "patch"
      else:
          print("No relevant files changed — skipping version bump")
          sys.exit(0)

      print(f"Bump type: {bump_type}")

      # Read current version
      doc = tomlkit.parse(Path("pyproject.toml").read_text())
      current_version = doc["project"]["version"]
      print(f"Current version: {current_version}")

      # Semver arithmetic
      match = re.fullmatch(r"v?(\\d+)\\.(\\d+)\\.(\\d+)", current_version)
      if not match:
          msg = f"Invalid version format: {current_version}"
          print(msg, file=sys.stderr)
          sys.exit(1)
      major = int(match.group(1))
      minor = int(match.group(2))
      patch = int(match.group(3))

      if bump_type == "major":
          new_version = f"{major + 1}.0.0"
      elif bump_type == "minor":
          new_version = f"{major}.{minor + 1}.0"
      else:
          new_version = f"{major}.{minor}.{patch + 1}"

      print(f"New version: {new_version}")

      # Update pyproject.toml
      doc["project"]["version"] = new_version
      Path("pyproject.toml").write_text(tomlkit.dumps(doc))

      # Update src/<package>/__init__.py
      init_files = list(Path("src").glob("*/__init__.py"))
      for init_path in init_files:
          content = init_path.read_text()
          pattern = r'__version__\\s*=\\s*["\\'][^"\\']+["\\']'
          if re.search(pattern, content):
              updated = re.sub(pattern, f'__version__ = "{new_version}"', content)
              init_path.write_text(updated)
              print(f"Updated {init_path}")

      # Commit and tag
      git_add = ["git", "add", "pyproject.toml"] + [str(p) for p in init_files]
      subprocess.run(git_add, check=True)
      commit_msg = f"chore: bump version to {new_version} [skip ci]"
      subprocess.run(["git", "commit", "-m", commit_msg], check=True)
      tag_msg = f"release {new_version}"
      subprocess.run(["git", "tag", "-a", f"v{new_version}", "-m", tag_msg], check=True)

      # Push changes and tag
      server = os.environ['CI_SERVER_HOST']
      project = os.environ['CI_PROJECT_PATH']
      token = os.environ['GITLAB_TOKEN']
      remote_url = f"https://gitlab-ci-token:{token}@{server}/{project}.git"
      subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)
      push_branch = f"HEAD:{os.environ['CI_COMMIT_BRANCH']}"
      subprocess.run(["git", "push", "origin", push_branch], check=True)
      subprocess.run(["git", "push", "origin", f"v{new_version}"], check=True)

      msg = (
          f"Successfully bumped version to {new_version} "
          f"and pushed tag v{new_version}"
      )
      print(msg)
      PYEOF
"""

_AGENTS_CONTENT = """\
# Project

## Documentation Hierarchy

This project uses a three-level documentation hierarchy. Documents are listed \
in order of authority — higher documents override lower ones when in conflict.

| Level | Document | Contains | Authority |
|-------|----------|----------|-----------|
| 1 | `docs/SPEC.md` | Requirements, constraints, scope | Highest |
| 2 | `docs/DESIGN.md` | Architecture, packages, interfaces | Medium |
| 3 | `docs/PATTERNS.md` | Code patterns, conventions, testing | Lowest |

**Rules:**
- SPEC.md must exist before DESIGN.md can be written
- DESIGN.md must exist before PATTERNS.md can be written
- When documents conflict, the higher-level document wins and lower documents \
must be amended

## Mandatory Development Workflow

All code changes — features, bug fixes, refactors — MUST follow this workflow:

### 1. Identify the Highest Affected Doc Level

- Does this change affect **requirements**? → Start at SPEC
- Does this change affect **architecture or packages**? → Start at DESIGN
- Does this change affect **code patterns**? → Start at PATTERNS
- Is this a **code-only change** with no doc impact? → Skip to step 5

### 2. Update Docs Top-Down

Starting from the highest affected level, tell the user to run the \
corresponding `prothon` CLI commands in order:

- SPEC-level change → `prothon spec`, then `prothon design`, then \
`prothon patterns`
- DESIGN-level change → `prothon design`, then `prothon patterns`
- PATTERNS-level change → `prothon patterns` only

Each command launches a separate assistant session. Do NOT invoke \
`/spec-writer`, `/design-writer`, or `/patterns-writer` directly — the user \
runs these via the CLI.

Doc harmonization and tech-researcher are handled automatically by the \
design-writer and patterns-writer skills as subagent quality gates. You do \
not need to trigger them manually.

### 5. Implement

Write the code changes.

### 6. Verify Compliance (Automatic)

**This is an always-on quality gate.** Before claiming any implementation \
work is complete, you MUST spawn a dedicated subagent (type: general-purpose, \
fresh context) to verify code matches documentation. Do not perform this \
check inline — spawn a fresh subagent: "Activate prothon-compliance-checker \
and produce a report." This ensures it gets a clean context focused solely \
on compliance verification. Report the subagent's findings to the user.

If the compliance check reports failures, fix the code or update docs and \
re-check.

For explicit full compliance scans, the user can run `prothon compliance`.

## Skills Directory

Project-specific reference skills live in `.agents/skills/` as directories \
containing `SKILL.md`. Claude Code, opencode, and Gemini CLI discover this \
directory natively — no symlinks or additional configuration needed.

When creating new skills, place them in \
`.agents/skills/<skill-name>/SKILL.md`.

## Conventions

- **Package manager:** uv
- **Task runner:** poe (poethepoet)
- **Linting:** ruff (linting + formatting)
- **Type checking:** ty
- **Testing:** pytest + hypothesis
- **Security:** bandit
- **Dead code:** vulture
- **Complexity:** complexipy
- **Pre-commit:** hooks enforce all checks on every commit

Run `poe check` before committing to verify all quality checks pass.
"""


def _template_dir() -> Path:
    """Return the path to the bundled template directory."""
    pkg_template = Path(__file__).resolve().parent / "template"
    if pkg_template.is_dir():
        return pkg_template
    # Development / mutmut: walk up to find template/ with copier.yml
    current = Path(__file__).resolve().parent
    while current != current.parent:
        candidate = current / "template"
        if candidate.is_dir() and (candidate / "copier.yml").exists():
            return candidate
        current = current.parent
    msg = "Cannot locate template directory"
    raise FileNotFoundError(msg)


def generate(dest: Path, data: dict | None = None) -> None:
    """Generate a project from the template using Copier.

    Args:
        dest: Destination directory for the generated project.
        data: Pre-filled answers dict. When provided, defaults=True
              is used to skip interactive prompts.
    """
    from copier import run_copy

    template = str(_template_dir())
    run_copy(
        template,
        str(dest),
        data=data,
        defaults=bool(data),
        unsafe=True,
        vcs_ref="HEAD",
    )
    _post_generate(dest)


def _post_generate(dest: Path) -> None:
    """Post-generation steps: symlinks, agent dirs, git init.

    Args:
        dest: The generated project root directory.
    """
    # Create symlinks for agent instruction files
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = dest / name
        if not link.exists():
            os.symlink("AGENTS.md", link)

    # Create .agents/skills for project-specific reference skills
    (dest / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

    # Initialize git
    run_git("init", cwd=dest)
    run_git("add", ".", cwd=dest)
    run_git("commit", "-m", "Initial commit from prothon template", cwd=dest)


def _collect_project_details() -> dict[str, str]:
    """Collect project details interactively using Typer prompts.

    Returns:
        Dict with module_name, description, author_name, author_email,
        python_version, and license.
    """
    import typer

    return {
        "module_name": typer.prompt("Module name"),
        "description": typer.prompt("Description"),
        "author_name": typer.prompt("Author name"),
        "author_email": typer.prompt("Author email"),
        "python_version": typer.prompt("Python version", default="3.12"),
        "license": typer.prompt("License", default="MIT"),
    }


def _run_copier_init(dest: Path, data: dict[str, str]) -> None:
    """Run Copier for project adoption (no git init, no commits).

    Args:
        dest: Destination directory for the generated files.
        data: Pre-filled answers dict from _collect_project_details().
    """
    from copier import run_copy

    run_copy(
        str(_template_dir()),
        str(dest),
        data=data,
        defaults=True,
        unsafe=True,
        skip_tasks=True,
        skip_if_exists=["**"],
        exclude=["docs/*", "AGENTS.md*"],
        vcs_ref="HEAD",
    )


def init_existing(cwd: Path | None = None) -> list[Path]:
    """Overlay the docs-first workflow onto an existing project.

    When pyproject.toml is absent (Path A), collects project details
    interactively and invokes Copier to scaffold the Python project structure
    before applying the common overlay. Files generated by Copier are not
    included in the returned list.

    When pyproject.toml is present (Path B), Copier is skipped and only
    the common overlay files are created.

    Args:
        cwd: Directory to adopt. Defaults to the current working directory.

    Returns:
        List of created file paths (excludes Copier-generated files in Path A).

    Raises:
        GitError: If the directory is not a git repository.
        ProjectAlreadyInitError: If docs/SPEC.md already exists.
    """
    root = Path(cwd) if cwd else Path.cwd()

    # Guard: must be a git repository
    try:
        run_git("rev-parse", "--git-dir", cwd=root)
    except GitError:
        raise GitError(f"not a git repository: {root}") from None

    # Guard: must not already be initialized
    spec_path = root / "docs" / "SPEC.md"
    if spec_path.exists():
        raise ProjectAlreadyInitError(f"docs/SPEC.md already exists in {root}")

    created: list[Path] = []

    # Path A: no pyproject.toml -> scaffold Python structure via Copier
    if not (root / "pyproject.toml").exists():
        answers = _collect_project_details()
        _run_copier_init(root, answers)

    # Create docs/ directory and write scaffolds
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    scaffolds = {
        "SPEC.md": _SPEC_SCAFFOLD,
        "DESIGN.md": _DESIGN_SCAFFOLD,
        "PATTERNS.md": _PATTERNS_SCAFFOLD,
    }
    for filename, content in scaffolds.items():
        path = docs_dir / filename
        path.write_text(content)
        created.append(path)

    # Create AGENTS.md at project root
    agents_path = root / "AGENTS.md"
    agents_path.write_text(_AGENTS_CONTENT)
    created.append(agents_path)

    # Create symlinks: CLAUDE.md, GEMINI.md, AGENT.md -> AGENTS.md
    for name in ("CLAUDE.md", "GEMINI.md", "AGENT.md"):
        link = root / name
        if link.is_symlink():
            link.unlink()
        os.symlink("AGENTS.md", link)
        created.append(link)

    # Create .agents/skills/ directory
    skills_dir = root / ".agents" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    created.append(skills_dir)

    # Add version-bump CI workflow if not already present
    workflow_path = root / ".github" / "workflows" / "version-bump.yml"
    if not workflow_path.exists():
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(_VERSION_BUMP_WORKFLOW)
        created.append(workflow_path)

    # Add version-tag CI workflow if not already present
    tag_workflow_path = root / ".github" / "workflows" / "version-tag.yml"
    if not tag_workflow_path.exists():
        tag_workflow_path.parent.mkdir(parents=True, exist_ok=True)
        tag_workflow_path.write_text(_VERSION_TAG_WORKFLOW)
        created.append(tag_workflow_path)

    # Add GitLab CI version-bump workflow if no .gitlab-ci.yml exists
    gitlab_ci_path = root / ".gitlab-ci.yml"
    if not gitlab_ci_path.exists():
        gitlab_ci_path.write_text(_GITLAB_VERSION_BUMP)
        created.append(gitlab_ci_path)

    # Append [tool.prothon.ci] to pyproject.toml if it exists and lacks the section
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        _ensure_prothon_ci_section(pyproject_path)

    return created


def _ensure_prothon_ci_section(pyproject_path: Path) -> None:
    """Append [tool.prothon.ci] with auto_version = true if absent.

    Args:
        pyproject_path: Path to pyproject.toml to modify in place.
    """
    doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))
    tool = doc.get("tool")
    prothon_section = tool.get("prothon") if isinstance(tool, dict) else None
    ci_section = (
        prothon_section.get("ci") if isinstance(prothon_section, dict) else None
    )
    if ci_section is not None:
        return
    if not isinstance(tool, dict):
        tool = tomlkit.table(is_super_table=True)
        doc.add("tool", tool)
    if not isinstance(prothon_section, dict):
        prothon_section = tomlkit.table(is_super_table=True)
        tool.add("prothon", prothon_section)
    ci = tomlkit.table()
    ci.add(
        tomlkit.comment("Set to false to disable automatic version bumping"),
    )
    ci.add("auto_version", True)
    prothon_section.add("ci", ci)
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
