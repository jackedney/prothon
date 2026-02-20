---
name: tech-hypothesis
description: Reference guide for Hypothesis -- property-based testing for Python
user-invocable: false
---

# Hypothesis

> Purpose: Property-based testing to complement example-based pytest tests (R4: scaffolded toolchain)
> Docs: https://hypothesis.readthedocs.io/
> Version researched: >=6.0 (latest 6.151.8)

## Quick Start

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.integers(), st.integers())
def test_addition_is_commutative(a: int, b: int):
    assert a + b == b + a
```

Hypothesis generates random test inputs based on strategies and shrinks failing cases to the smallest reproducer.

## Common Patterns

### Common strategies for this project

```python
from hypothesis import strategies as st

# Strings for module names, paths, identifiers
st.text(min_size=1, max_size=100)
st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)  # valid Python identifiers

# Paths and filenames
st.text(alphabet=st.characters(categories=("L", "N"), whitelist_characters="_-./"))

# Integers for task indices, line counts
st.integers(min_value=0, max_value=100)

# Booleans for completed/pending flags
st.booleans()

# Lists for file lists
st.lists(st.text(min_size=1), min_size=0, max_size=20)

# Dictionaries for TOML-like data
st.dictionaries(st.text(min_size=1), st.text())
```

### Testing data model invariants

```python
from hypothesis import given
from hypothesis import strategies as st
from prothon.promise import Task

@given(
    title=st.text(min_size=1, max_size=200),
    lines_added=st.integers(min_value=0, max_value=10000),
    lines_removed=st.integers(min_value=0, max_value=10000),
)
def test_task_line_count_tolerance(title: str, lines_added: int, lines_removed: int):
    """Tolerance is +-30% or +-30 lines, whichever is greater."""
    tolerance = max(int(lines_added * 0.3), 30)
    assert lines_added - tolerance <= lines_added <= lines_added + tolerance
```

### Composite strategies for complex objects

```python
from hypothesis import strategies as st
from hypothesis.strategies import composite

@composite
def task_strategy(draw):
    """Generate a valid Task-like dict."""
    return {
        "title": draw(st.text(min_size=1, max_size=100)),
        "completed": draw(st.booleans()),
        "attempts": draw(st.integers(min_value=0, max_value=10)),
        "files_to_create": draw(st.lists(st.text(min_size=1), max_size=5)),
        "files_to_modify": draw(st.lists(st.text(min_size=1), max_size=5)),
        "files_to_remove": draw(st.lists(st.text(min_size=1), max_size=5)),
    }

@given(task=task_strategy())
def test_task_roundtrip(task):
    """Serializing and deserializing preserves all fields."""
    ...
```

### Filtering with assume()

```python
from hypothesis import given, assume
from hypothesis import strategies as st

@given(st.text())
def test_non_empty_module_name(name: str):
    assume(len(name) > 0)  # discard empty strings
    assume(name.isidentifier())  # discard invalid identifiers
    # test with valid module names only
```

### Settings for control

```python
from hypothesis import given, settings
from hypothesis import strategies as st

@settings(max_examples=500, deadline=None)  # more examples, no time limit
@given(st.text())
def test_thorough_parsing(text: str):
    ...

@settings(max_examples=50)  # fewer examples for slow tests
@given(st.text())
def test_expensive_operation(text: str):
    ...
```

## Gotchas & Pitfalls

- **Hypothesis tests are slower than example-based tests.** Default is 100 examples per test. Use `@settings(max_examples=N)` to tune. Consider `deadline=None` for tests involving I/O.
- **`assume()` discards test cases, not fails them.** Too many `assume()` calls make tests slow (Hypothesis must generate many candidates to find valid ones). Prefer constrained strategies over filtering.
- **Flaky test detection.** Hypothesis re-runs failing cases from a database (`.hypothesis/` directory). Add `.hypothesis/` to `.gitignore`. If a test passes locally but fails in CI, the database divergence is usually the cause.
- **`@given` does not compose with `@pytest.mark.parametrize`.** Use `st.sampled_from()` inside the strategy instead.
- **Stateful testing exists but is advanced.** Use `RuleBasedStateMachine` for testing stateful APIs. Overkill for most prothon modules.
- **Text strategy can generate surprising Unicode.** If your code only handles ASCII, use `st.text(alphabet=st.characters(categories=("L", "N")))` or `st.from_regex()`.

## Idiomatic Usage

**Do:** Use Hypothesis for roundtrip properties (serialize/deserialize), invariant checking (e.g., line count tolerance), and input validation (reject bad input gracefully).

**Don't:** Replace all example-based tests with property tests. Use property tests for "this should hold for all inputs" and example tests for specific known cases.

**Do:** Write custom composite strategies for domain objects (Task, Promise, etc.) and reuse them across tests.

**Don't:** Use `assume()` as the primary filtering mechanism -- constrain strategies at construction time.

**Do:** Set `deadline=None` for tests involving filesystem or subprocess operations.
