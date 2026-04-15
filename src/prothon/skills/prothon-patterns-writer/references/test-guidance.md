# Test Guidance Reference

Detailed guidance for writing the Testing Patterns section of PATTERNS.md.

## Test Value Guidance

When writing the Testing Patterns section, include explicit guidance on what NOT to test. The goal is fewer, higher-value tests — not comprehensive coverage of every line.

**Do NOT test:**
- Trivial code: simple attribute access, getters/setters, one-line assignments, pass-through functions
- Language features: that `+` adds numbers, that `dict[key]` retrieves values
- Framework behavior: that FastAPI routes return responses, that Pydantic validates types
- Redundant coverage: the same logic tested at multiple levels (unit + integration + e2e for identical paths)
- Implementation details: private methods called by tested public methods

**Focus tests on:**
- Business logic: conditional branches, calculations, state transitions
- Edge cases: boundary conditions, error handling, malformed input
- Integration points: how components interact, contract compliance
- Invariants: properties that must always hold

## Lightweight, Fast Tests

Tests must be cheap to run. The full suite should complete in seconds, not minutes.

**Keep tests lightweight:**
- Use fakes/stubs instead of real services (no database connections, no HTTP servers, no filesystem writes to real paths)
- Prefer in-memory structures: `io.StringIO` over temp files, `dict` over real caches
- Avoid loading heavy dependencies in unit tests — mock at the boundary
- Isolate units so each test exercises one module, not the entire dependency graph
- Reset state between tests; never rely on test execution order

**Fast test patterns:**
- Protocol fakes over real implementations (e.g., `FakeGitDiff` instead of subprocess calls)
- Fixture scope: use `@pytest.fixture(scope="function")` as default; promote to session/class only when setup is expensive and stateless
- Skip slow tests by default: mark with `@pytest.mark.slow` and run via `pytest -m "not slow"` in CI fast paths
- Parallel execution: structure tests so `pytest-xdist` works (no shared mutable state)

**One test file per source module is NOT required.** Test files should map to cohesive units of behavior, not file names. A complex module may need multiple test files; a trivial module may need none.
