---
name: tech-tomlkit
description: Reference guide for tomlkit — TOML read/write with comment and formatting preservation
user-invocable: false
---

# tomlkit

> Purpose: TOML read/write with comment and formatting preservation (R17-R18: change promise contract)
> Docs: https://tomlkit.readthedocs.io/
> Version researched: >=0.13,<1.0 (latest 0.13.2)

## Quick Start

```python
import tomlkit

# Read existing TOML (preserves comments, whitespace, ordering)
content = Path("config.toml").read_text()
doc = tomlkit.parse(content)

# Modify and write back (formatting preserved)
doc["metadata"]["completed"] = True
Path("config.toml").write_text(tomlkit.dumps(doc))
```

Or use `TOMLFile` for file I/O:

```python
from tomlkit import TOMLFile

f = TOMLFile("config.toml")
doc = f.read()
doc["key"] = "value"
f.write(doc)
```

## Common Patterns

### Parse and modify existing documents

```python
doc = tomlkit.parse(toml_string)

# Dict-like access
doc["metadata"]["base_commit"] = "abc123"
doc["tasks"][0]["completed"] = True
doc["tasks"][0]["attempts"] = 3

# Serialize back (preserves original formatting)
output = tomlkit.dumps(doc)
```

### Build documents from scratch

```python
doc = tomlkit.document()
doc.add(tomlkit.comment("Change promise contract"))
doc.add(tomlkit.nl())

# Add a table
meta = tomlkit.table()
meta.add("base_commit", "abc123")
meta.add("created_at", "2026-02-19T10:00:00Z")
doc.add("metadata", meta)

# Add array of tables ([[tasks]])
tasks = tomlkit.aot()
task = tomlkit.table()
task.add("title", "implement scaffold")
task.add("completed", False)
task.add("files_to_create", ["src/scaffold.py"])
tasks.append(task)
doc.add("tasks", tasks)
```

### TOMLFile for clean file I/O

```python
from tomlkit import TOMLFile

f = TOMLFile("docs/change_promise.toml")
doc = f.read()
# ... modify doc ...
f.write(doc)
```

### Creating typed items explicitly

```python
# When you need control over TOML representation
tomlkit.integer(42)
tomlkit.float_(3.14)
tomlkit.string("hello", literal=True)       # 'hello' (single quotes)
tomlkit.string("multi\nline", multiline=True) # triple-quoted
tomlkit.array()                               # empty []
tomlkit.table()                               # empty table
tomlkit.aot()                                 # empty [[array of tables]]
tomlkit.comment("This is a comment")
tomlkit.nl()                                  # newline
```

## Gotchas & Pitfalls

- **`tomlkit.parse()` returns a `TOMLDocument`, not a plain dict.** It looks and acts like a dict but carries formatting metadata. Passing it to code that checks `isinstance(x, dict)` will fail — use `isinstance(x, MutableMapping)` or duck typing.
- **Assigning plain Python values auto-wraps them.** `doc["key"] = 42` works and creates a tomlkit `Integer`. But if you need specific formatting (e.g., literal strings, multiline), use explicit constructors like `tomlkit.string()`.
- **Array of tables (`[[section]]`) use `aot()`, not `array()`.** `array()` is for inline arrays (`key = [1, 2, 3]`). `aot()` is for repeated table headers. Mixing them up produces invalid TOML.
- **`dumps()` returns a string, not bytes.** Write with `Path.write_text()`, not `write_bytes()`.
- **Deleting keys preserves surrounding whitespace/comments.** This is usually desirable but can leave orphaned comments if the comment was meant to describe the deleted key.
- **Performance: ~18x slower than `tomllib` for parsing.** Irrelevant for small config files (<100KB) but matters if parsing thousands of files. Use `tomllib` for read-only bulk parsing.

## Idiomatic Usage

**Do:** Use `tomlkit.parse()` + `tomlkit.dumps()` for roundtrip editing of human-authored files. This preserves the author's formatting choices.

**Don't:** Use `tomlkit` for read-only access — use stdlib `tomllib` instead (faster, simpler, no dependency).

**Do:** Use `tomlkit.document()` + builder helpers to construct new TOML files programmatically with clean formatting.

**Don't:** Build TOML strings manually with f-strings or string concatenation. The builder API handles escaping and formatting correctly.

**Do:** Use `TOMLFile` when the read-modify-write cycle targets a single file path — it handles encoding consistently.
