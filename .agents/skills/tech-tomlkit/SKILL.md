---
name: tech-tomlkit
description: Reference guide for tomlkit -- TOML read/write with comment and formatting preservation
user-invocable: false
---

# tomlkit

> Purpose: TOML read/write with comment and formatting preservation (R25-R26: change promise contract)
> Docs: https://tomlkit.readthedocs.io/
> Version researched: >=0.13,<1.0 (latest 0.13.2)

## Quick Start

```python
import tomlkit
from pathlib import Path

# Read existing TOML (preserves comments, whitespace, ordering)
content = Path("config.toml").read_text()
doc = tomlkit.parse(content)

# Modify and write back (formatting preserved)
doc["metadata"]["completed"] = True
Path("config.toml").write_text(tomlkit.dumps(doc))
```

Or use `TOMLFile` for cleaner file I/O:

```python
from tomlkit import TOMLFile

f = TOMLFile("config.toml")
doc = f.read()
doc["key"] = "value"
f.write(doc)
```

`tomlkit.loads()` and `tomlkit.parse()` are aliases -- both accept a TOML string or bytes and return a `TOMLDocument`.

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

### Adding comments and whitespace

```python
doc = tomlkit.document()

# Standalone comment
doc.add(tomlkit.comment("Configuration file"))
doc.add(tomlkit.nl())

# Inline comment on a value
doc["debug"] = True
doc.item("debug").comment("Set to false in production")

# Comment inside a table
server = tomlkit.table()
server.add(tomlkit.comment("Server settings"))
server["host"] = "localhost"
doc["server"] = server
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

### Serialization with sort_keys

```python
# From a plain Python dict (no formatting metadata)
config = {"server": {"host": "0.0.0.0", "port": 3000}}
output = tomlkit.dumps(config, sort_keys=True)

# From a TOMLDocument (preserves original ordering)
doc = tomlkit.parse(content)
output = tomlkit.dumps(doc)  # do NOT use sort_keys on human-authored files
```

## Gotchas & Pitfalls

- **`tomlkit.parse()` returns a `TOMLDocument`, not a plain dict.** It looks and acts like a dict but carries formatting metadata. Code that checks `isinstance(x, dict)` will fail -- use `isinstance(x, MutableMapping)` or duck typing instead.
- **Array of tables (`[[section]]`) use `aot()`, not `array()`.** `array()` is for inline arrays (`key = [1, 2, 3]`). `aot()` is for repeated table headers. Mixing them up produces invalid TOML.
- **`dumps()` returns a string, not bytes.** Write with `Path.write_text()`, not `write_bytes()`.
- **Assigning plain Python values auto-wraps them.** `doc["key"] = 42` works. But for specific formatting (literal strings, multiline), use explicit constructors like `tomlkit.string()`.
- **Deleting keys preserves surrounding whitespace/comments.** Usually desirable but can leave orphaned comments.
- **Performance: ~18x slower than `tomllib` for parsing.** Irrelevant for small config files but matters for bulk parsing. Use stdlib `tomllib` for read-only access when formatting preservation is not needed.
- **`as_string()` and `dumps()` produce the same output** for a `TOMLDocument`. Use `dumps()` for consistency with the `loads()`/`dumps()` naming convention.

## Idiomatic Usage

**Do:** Use `tomlkit.parse()` + `tomlkit.dumps()` for roundtrip editing of human-authored files.

**Don't:** Use `tomlkit` for read-only access -- use stdlib `tomllib` instead (faster, no dependency).

**Do:** Use `tomlkit.document()` + builder helpers to construct new TOML files programmatically with clean formatting.

**Don't:** Build TOML strings manually with f-strings or concatenation. The builder API handles escaping and formatting correctly.

**Do:** Use `TOMLFile` when the read-modify-write cycle targets a single file path.

**Do:** Use `item().comment("...")` to attach inline comments when scaffolding TOML from scratch.
```python
doc["server"]["ssl"] = True
doc["server"].item("ssl").comment("Enable SSL")
```

**Don't:** Use `sort_keys=True` on `dumps()` for human-authored files -- it destroys intentional ordering. Reserve sorting for machine-generated output only.
