---
name: optim-subprocess-management
description: Optimisation patterns for subprocess management -- git CLI and assistant invocation
user-invocable: false
---

# Subprocess Management Optimisation

> Relevance: Prothon shells out to git for every verification check and to AI assistants for every agent session. Poor subprocess handling causes hangs, orphaned processes, and confusing error messages. (SPEC R7, R21, R25)

## Key Principles

1. **Fail fast with clear errors.** Every subprocess call must handle non-zero exit codes and translate them into actionable error messages. Silent failures cause cascading confusion.
2. **Never block on unbounded input.** Subprocesses that prompt for input (git credential helpers, assistant login flows) must be prevented or timed out.
3. **Use list-form arguments, never shell=True.** List-form prevents shell injection and makes argument escaping predictable.

## Recommended Patterns

### Centralised subprocess wrapper

```python
# Naive: scattered subprocess calls with inconsistent error handling
result = subprocess.run(["git", "diff", "--numstat"], capture_output=True, text=True)
if result.returncode != 0:
    raise Exception(result.stderr)

# Optimised: centralised wrapper with consistent error handling
def run_git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return stdout. Raises GitError on failure."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode != 0:
        raise GitError(args[0], result.stderr.strip())
    return result.stdout
```

### Preventing interactive prompts

```python
# Naive: git may block waiting for credentials
subprocess.run(["git", "push"])

# Optimised: disable terminal prompts
env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
subprocess.run(["git", "push"], env=env, capture_output=True, text=True)
```

### Machine-readable output flags

```python
# Naive: parse human-readable git output (fragile)
output = run_git("diff", "--stat")

# Optimised: use machine-readable flags
output = run_git("diff", "--numstat")       # tab-separated: added\tremoved\tfile
output = run_git("diff", "--name-only")     # one file path per line
output = run_git("status", "--porcelain")   # fixed-width status codes
```

### Assistant subprocess lifecycle

```python
# Naive: fire and forget
subprocess.Popen(["claude", "--skill", skill_name])

# Optimised: wait for completion, check exit code, handle interrupts
try:
    result = subprocess.run(
        command,
        cwd=project_root,
        check=False,
    )
    if result.returncode != 0:
        raise AssistantError(f"{name} exited with code {result.returncode}")
except KeyboardInterrupt:
    raise  # let the subprocess handle its own cleanup
```

### Binary existence check

```python
import shutil

def _check_binary(name: str) -> Path:
    path = shutil.which(name)
    if path is None:
        raise AssistantNotFoundError(f"{name} not found on PATH. Install it first.")
    return Path(path)
```

## Data Structure Choices

- **`subprocess.run()` over `Popen`** for all synchronous operations. `run()` handles wait/communicate correctly. Use `Popen` only for truly concurrent processes.
- **`capture_output=True` over separate `PIPE` arguments.** Equivalent but more readable.
- **Omit `capture_output` for interactive assistant sessions** that need stdin/stdout passthrough.

## Measurement

- **Time individual subprocess calls** in debug mode to identify slow operations.
- **Count subprocess invocations per command** -- if a single prothon command spawns >10 git subprocesses, consider batching (e.g., one `git diff --numstat` covers all files vs. per-file `git show`).
- **Profile with `time prothon compliance`** to find bottlenecks. Subprocess overhead is typically 5-50ms per call on Linux.

## Common Pitfalls

- **Forgetting `text=True`** -- without it, stdout/stderr are `bytes`, causing `str` method calls to fail or produce `b'...'` in error messages.
- **Using `shell=True` for convenience** -- introduces shell injection risk and platform-dependent behavior.
- **Not setting `cwd` explicitly** -- fragile when prothon is invoked from subdirectories.
- **Ignoring stderr on success** -- some git commands write warnings to stderr even on exit code 0. Don't treat non-empty stderr as an error.
- **Deadlocks with `Popen` and `PIPE`** -- if using `Popen` with `stdout=PIPE` and `stderr=PIPE`, you must read both or use `communicate()`.
