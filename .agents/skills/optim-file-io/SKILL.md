---
name: optim-file-io
description: Optimisation patterns for file I/O -- symlinks, path resolution, and template rendering
user-invocable: false
---

# File I/O Optimisation

> Relevance: Prothon manages symlinks for skill discovery, resolves project roots by walking parent directories, renders Jinja2 templates, and reads/writes TOML promise files. Incorrect path handling causes subtle cross-platform bugs and broken skill discovery. (SPEC R36-R39, R42-R43; DESIGN: skills.py, project.py, per-backend symlink strategy)

## Key Principles

1. **Use `pathlib.Path` everywhere.** String path manipulation with `os.path.join()` is error-prone. `Path` objects are composable, cross-platform, and type-checkable.
2. **Resolve symlinks explicitly when needed.** `Path.resolve()` follows symlinks and makes paths absolute. Use it for comparison and existence checks. Use `Path.readlink()` to inspect symlink targets.
3. **Fail on missing paths early.** Check existence before operating rather than catching `FileNotFoundError` deep in a call stack.

## Recommended Patterns

### Project root detection by walking up

```python
# Naive: assume cwd is the project root
root = Path.cwd()

# Optimised: walk up looking for a marker file
def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / "docs" / "SPEC.md").exists():
            return parent
    raise ProjectNotFoundError("No docs/SPEC.md found in parent directories")
```

### Symlink management for skill discovery (per-backend strategy)

Per DESIGN.md, each backend maintains its own set of direct symlinks from its discovery directory to bundled package directories. No shared central location.

```python
# Naive: create symlink without checking existing state
target.symlink_to(source)

# Optimised: handle existing symlinks, broken symlinks, and real files
def ensure_symlink(source: Path, target: Path) -> None:
    """Create or update a symlink. Handles broken and stale links."""
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return  # already correct
        target.unlink()  # stale or wrong target
    elif target.exists():
        raise SkillConflictError(f"{target} exists and is not a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)
```

Backend-specific targets:
- Claude Code: `~/.claude/skills/`
- opencode: `~/.config/opencode/skills/` (respects `$XDG_CONFIG_HOME`)

### Safe file writing with atomic semantics

```python
# Naive: write directly (corruption on crash/interrupt)
path.write_text(content)

# Optimised: write to temp file, then rename (atomic on same filesystem)
import tempfile

def write_atomic(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        Path(tmp).replace(path)  # atomic rename on POSIX
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
```

### Directory traversal for skill discovery

```python
# Naive: glob with string matching
skills = list(Path("skills").glob("**/SKILL.md"))

# Optimised: iterate immediate subdirs only (skills are one level deep)
def discover_skills(skills_dir: Path) -> list[Path]:
    """Find all skill directories containing SKILL.md."""
    if not skills_dir.is_dir():
        return []
    return [
        d for d in sorted(skills_dir.iterdir())
        if d.is_dir() and (d / "SKILL.md").exists()
    ]
```

### Path comparison

```python
# Naive: compare string representations (breaks with symlinks, relative paths)
if str(path1) == str(path2):

# Optimised: resolve both paths before comparing
if path1.resolve() == path2.resolve():
```

## Data Structure Choices

- **`Path` over `str`** for all filesystem paths. Type checkers catch misuse. Methods like `.parent`, `.name`, `.suffix` eliminate string manipulation.
- **`Path.iterdir()` over `os.listdir()`** -- returns `Path` objects directly, no join needed.
- **`Path.read_text()` / `Path.write_text()`** for small files. For large files or streaming, use `open()` with context manager.
- **`shutil.copytree()` with `dirs_exist_ok=True`** (Python 3.8+) for recursive directory copy without pre-cleanup.

## Measurement

- **Count filesystem operations** per CLI command. If `find_project_root()` is called multiple times, cache the result.
- **Profile symlink operations** -- `sync_skills()` should complete in <100ms for 10 skills. Symlink creation is fast; existence checks dominate.
- **Check I/O pattern** -- multiple `Path.read_text()` calls on the same file indicate a caching opportunity.

## Common Pitfalls

- **`Path.exists()` returns `False` for broken symlinks.** Use `Path.is_symlink()` to detect symlinks regardless of target validity.
- **`Path.resolve()` follows symlinks.** If you need the symlink path itself, do not resolve. Use `Path.readlink()` to get the target.
- **`mkdir(parents=True, exist_ok=True)` is idempotent.** Always use both flags unless you specifically need to detect pre-existing directories.
- **`Path.relative_to()` raises `ValueError` if not a subpath.** Guard with a try/except or check `is_relative_to()` first (Python 3.9+).
- **Template rendering can produce empty files.** Always validate that rendered output is non-empty before writing, especially for critical files like `pyproject.toml`.
