# Implementation Patterns

## Code Organization

### Module Layout

Prefer a flat structure — one module per subsystem, except where a logical subpackage is needed (e.g., `src/prothon/checks/` groups related static compliance checks). The concrete list of modules and their responsibilities is maintained in DESIGN.md. Domain modules remain plain Python, independent of the CLI framework.

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | lowercase, singular nouns | `promise.py`, `ui.py`, `config.py` |
| Functions | `verb_noun` | `resolve_agent()`, `render_compliance_report()` |
| Private helpers | `_verb_noun` | `_git_diff_names()`, `_within_tolerance()` |
| Classes | PascalCase, no suffix noise | `CheckResult`, `Promise`, `Task` |
| Backend Classes | `<Name>Backend` | `ClaudeBackend`, `GeminiBackend` |
| Constants | `UPPER_SNAKE` at module level | `PROMISE_PATH`, `DEFAULT_TOLERANCE` |
| Type aliases | PascalCase | `DiffStat = dict[str, tuple[int, int]]` |

### Import Order

Four groups, separated by blank lines, each group alphabetical: (1) `from __future__ import annotations` in every file, (2) stdlib, (3) third-party, (4) local with explicit names — no star imports.

### Module API Surface

Each module exposes a minimal public API. Internal helpers use the `_` prefix.

**cli.py:**
```python
app: typer.Typer        # Main CLI entry point
promise_app: typer.Typer  # `prothon promise` subcommands
ci_app: typer.Typer       # `prothon ci` subcommands
```

**commands.py:**
```python
def spec_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def design_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def patterns_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def execute_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
def compliance_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> None: ...
def refactor_command(root: Path, agent: str | None, model: str | None, provider: str | None) -> int: ...
```

**ui.py:**
```python
def render_check_report(report: TaskCheckReport) -> Table: ...
def render_compliance_report(report: ComplianceReport) -> Table: ...
def render_plan(p: Promise) -> Table: ...
def render_status(promise: Promise) -> Table: ...
```

**config.py:**
```python
def file_hash(path: Path) -> str | None: ...
def find_init_path(root: Path, project_name: str, module_name: str) -> Path | None: ...
def read_toml(path: Path) -> dict: ...
def nested_get(doc: dict, *keys: str) -> str | None: ...
def resolve_agent(cli_value: str | None = None) -> str: ...
def resolve_model(cli_model: str | None, cli_provider: str | None) -> str | None: ...
```

**assistant.py:**
```python
def register_backend(name: str, cls: type) -> None: ...
def get_backend(name: str = "claude-code") -> AssistantBackend: ...
def launch(backend: AssistantBackend, skill_name: str, cwd: Path, model: str | None = None) -> int: ...
```

**checks/ (subpackage):**

The `checks` package re-exports all public symbols via `__all__`. The primary entry point is `run_static_checks`; individual `check_*` functions and `analyze_python_file` are also available for targeted use.

```python
def run_static_checks(root: Path) -> ComplianceReport: ...
def analyze_python_file(path: Path) -> dict[str, Any]: ...
def check_adoption_intelligence(root: Path) -> list[CheckResult]: ...
def check_agent_files(root: Path) -> list[CheckResult]: ...
def check_doc_existence(root: Path) -> list[CheckResult]: ...
def check_doc_harmonizer(root: Path) -> list[CheckResult]: ...
def check_execute_logic(root: Path) -> list[CheckResult]: ...
def check_inheritance(root: Path) -> list[CheckResult]: ...
def check_package_structure(root: Path) -> list[CheckResult]: ...
def check_patterns_doc(patterns_path: Path) -> list[CheckResult]: ...
def check_pre_commit(root: Path) -> list[CheckResult]: ...
def check_refactor_logic(root: Path) -> list[CheckResult]: ...
def check_semantic_versioning(root: Path) -> list[CheckResult]: ...
def check_skills_dir(root: Path) -> list[CheckResult]: ...
def check_tech_researcher(root: Path) -> list[CheckResult]: ...
```

**refactor.py:**
```python
def discover_drift(root: Path) -> list[DriftFinding]: ...
def collect_module_metrics(root: Path) -> list[ModuleMetrics]: ...
def collect_pattern_usage(root: Path) -> list[PatternOccurrence]: ...
def collect_cross_module_similarities(root: Path) -> list[SimilarityGroup]: ...
def generate_refactor_promise(root: Path, findings: list[DriftFinding]) -> Promise: ...
```

**scaffold.py:**
```python
def get_template_dir() -> Path: ...
def generate(dest: Path, data: dict | None = None) -> None: ...
```

**scaffold_cli.py:**
```python
def new_project(destination: str = ".") -> None: ...
def init_project(cwd: Path | None = None) -> None: ...
```

**git.py:**
```python
DiffStat = dict[str, tuple[int, int]]

class GitDiffProvider(Protocol):
    def diff_names(self, base_commit: str, *paths: str) -> set[str]: ...
    def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat: ...

def run_git(*args: str, cwd: Path | None = None) -> str: ...

class SubprocessGitDiff:
    def diff_names(self, base_commit: str, *paths: str) -> set[str]: ...
    def diff_numstat(self, base_commit: str, *paths: str) -> DiffStat: ...

def rev_parse_head(cwd: Path | None = None) -> str: ...
def is_dirty(path: Path, cwd: Path | None = None) -> bool: ...
def commit_file(path: Path, message: str, cwd: Path | None = None) -> None: ...
```

**versioning.py:**
```python
def parse_version(v: str) -> tuple[int, int, int]: ...
def bump_major(v: str) -> str: ...
def bump_minor(v: str) -> str: ...
def bump_patch(v: str) -> str: ...
def update_pyproject_version(path: Path, new_version: str) -> None: ...
def update_init_version(path: Path, new_version: str) -> None: ...
def create_tag(version: str, cwd: Path | None = None) -> None: ...
def detect_bump_type(before_sha: str, after_sha: str, cwd: Path | None = None) -> str | None: ...
```

**promise_verify.py:**
```python
DEFAULT_TOLERANCE = 30

class CheckStatus(Enum):
    PASSED = "PASS"
    FAILED = "FAIL"
    SKIPPED = "SKIP"

@dataclass
class FileCheckDetail:
    path: str
    expected_state: str
    actual_state: str
    status: CheckStatus

@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: str
    file_details: list[FileCheckDetail] = field(default_factory=list)

@dataclass
class TaskCheckReport:
    task_index: int
    title: str
    task_id: str
    checks: list[CheckResult] = field(default_factory=list)
    @property
    def passed(self) -> bool: ...
    def format(self) -> str: ...

def check_task(task_index: int, *, diff: GitDiffProvider | None = None, path: Path | None = None, promise: Promise | None = None) -> TaskCheckReport: ...
```

**adoption.py:**
```python
def init_existing(cwd: Path | None = None, data: dict[str, str] | None = None) -> list[Path]: ...
```

**ast_miner.py:**
```python
class IdiomMatcher:
    def __init__(self) -> None: ...
    def is_idiom_name(self, name: str) -> bool: ...
    def is_idiom_node(self, node: ast.AST) -> bool: ...
    def is_idiom_decorator(self, node: ast.AST) -> bool: ...

class ASTPatternMiner:
    def __init__(self, matcher: IdiomMatcher | None = None) -> None: ...
    def scan_directory(self, root: Path) -> str: ...
    def extract_from_file(self, path: Path) -> str: ...
```

**project.py:**
```python
def find_project_root(start: Path | None = None) -> Path: ...
```

**exceptions.py:**
```python
class ProthonError(Exception): ...
class ProjectNotFoundError(ProthonError): ...
class ProjectAlreadyInitError(ProthonError): ...
class PromiseError(ProthonError): ...
class AssistantNotFoundError(ProthonError): ...
class UnknownBackendError(ProthonError): ...
class ComplianceError(ProthonError): ...
class GitError(ProthonError): ...
class VersionError(ProthonError): ...
class MaxAttemptsExceeded(PromiseError): ...
```

**skills.py:**
```python
def bundled_skills_dir() -> Path: ...
def sync_skills(target: Path | None = None) -> None: ...
```

**compliance.py:**
```python
class CheckStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"

class CheckType(Enum):
    STATIC = "STATIC"
    SEMANTIC = "SEMANTIC"

@dataclass
class Requirement:
    source: str
    statement: str
    requirement_id: str | None = None

@dataclass
class CheckResult:
    requirement: Requirement
    status: CheckStatus
    check_type: CheckType = CheckType.STATIC
    evidence: str = ""
    rationale: str = ""
    def __str__(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckResult": ...

@dataclass
class ComplianceReport:
    results: list[CheckResult] = field(default_factory=list)
    @property
    def passed(self) -> bool: ...
    @property
    def score(self) -> float: ...
    @property
    def failures(self) -> list[CheckResult]: ...
    def results_by_source(self, source: str) -> list[CheckResult]: ...
    def results_by_type(self, check_type: CheckType) -> list[CheckResult]: ...
    @property
    def static_results(self) -> list[CheckResult]: ...
    @property
    def semantic_results(self) -> list[CheckResult]: ...
    def merge(self, other: "ComplianceReport") -> None: ...
    def add_from_dicts(self, findings: list[dict[str, Any]]) -> None: ...
    def format_summary(self) -> str: ...
```

**models.py:**
```python
PROMISE_PATH = Path("docs/change_promise.toml")

@dataclass
class Task:
    title: str
    task_id: str = field(default_factory=_generate_id)
    goal: str = ""
    success_criteria: str = ""
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    files_to_remove: list[str] = field(default_factory=list)
    expected_lines_added: int = 0
    expected_lines_removed: int = 0
    context_files: list[str] = field(default_factory=list)
    doc_sections: list[str] = field(default_factory=list)
    reference_skills: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    completed: bool = False
    attempts: int = 0
    max_attempts: int = 3

@dataclass
class Metadata:
    base_commit: str = ""
    created_at: str = ""

@dataclass
class Promise:
    metadata: Metadata = field(default_factory=Metadata)
    tasks: list[Task] = field(default_factory=list)
```

## Design Patterns

### Tiered Compliance Evidence Pattern
Compliance verification uses a hybrid strategy to map requirements to source code. **Static Analysis** (Regex/AST) performs fast, deterministic checks for structural rules and doc formats. **Semantic Analysis** (LLM-based) handles high-level functional requirements. Both feed into **Evidence Mapping**, where every result is paired with a `file:line` citation and a brief rationale.

### Progressive Disclosure Skill Pattern
To maintain context efficiency for AI assistants, generated reference skills follow a three-level hierarchy. **Level 1** (YAML frontmatter) provides trigger phrases for discovery. **Level 2** (`SKILL.md` body) contains core instructions. **Level 3** (`references/` subdirectory) holds detailed API specs and heavy examples, loaded only when needed.

### Refactor Wave Pattern
Changes must flow top-down through the documentation hierarchy: **DESIGN -> PATTERNS -> CODE**. Architectural shifts or convention changes are documented and approved first. Implementation tasks then reference the specific documentation heading they are aligning with.

### File Locking and Atomic Persistence
When parallel subagents mark tasks complete simultaneously, the promise TOML file is a shared resource. `complete_task()` wraps its load → modify → save cycle in an exclusive file lock to prevent lost updates, using a sibling `.toml.lock` file.

## Error Handling

### Centralized CLI Error Boundary
The `cli.py` module acts as the single catch-all boundary for `ProthonError` and its subclasses. Library modules raise exceptions; the CLI catches them, presents a formatted message, and terminates with a non-zero exit code.

### Terminal Failure Pattern
When a subagent reaches `max_attempts` for a task without passing verification and quality gates, it reports a terminal failure. The orchestrator records the failure and asks the user for a decision (skip, retry, or abort) to prevent infinite loops. As a programmatic backstop independent of skill-prompt compliance, `record_attempt()` enforces the `max_attempts` limit by raising `MaxAttemptsExceeded` (a subclass of `PromiseError`) when `attempts >= max_attempts`, preventing the counter from incrementing further.

### Data-Driven Doc Consistency Failures
Contradictions found by the `doc-harmonizer` are treated as data, not exceptions. They are presented as a structured report of `Conflict` objects, enabling interactive resolution and approval before any documents are amended.

### Model/Provider Resolution Errors
Configuration resolution for `opencode` enforces that both model and provider must be present if one is provided. Violations raise a `ConfigurationError` explaining the required format, ensuring early failure.

## Testing Patterns

### Test Value Over Test Count

Prioritize fewer, higher-value tests over comprehensive coverage. Not every line needs a test.

**Do NOT test:**
- Trivial code: simple attribute access, getters/setters, one-line assignments, pass-through functions that just delegate
- Language features: that `+` adds numbers, that `dict[key]` retrieves values, that `if` branches
- Framework behavior: that FastAPI routes return responses, that Pydantic validates types, that Typer parses CLI args
- Redundant coverage: the same conditional logic tested at unit, integration, and e2e levels with identical assertions
- Implementation details: private `_helper` methods already exercised through public method tests

**Focus tests on:**
- Business logic: conditional branches, calculations, state transitions, multi-step workflows
- Edge cases: boundary conditions, error handling paths, malformed input handling
- Integration points: how components interact, protocol compliance, contract boundaries
- Invariants: properties that must always hold regardless of input

**Test file organization:** One test file per source module is NOT required. Test files map to cohesive units of behavior, not file names. A complex module may warrant multiple test files (`test_auth_flows.py`, `test_auth_edge_cases.py`); a trivial module with no logic may need no test file at all.

### Lightweight, Fast Tests

Tests must be cheap to run. The full suite should complete in seconds, not minutes.

**Keep tests lightweight:**
- Use fakes/stubs instead of real services (no database connections, no HTTP servers, no filesystem writes to real paths)
- Prefer in-memory structures: `io.StringIO` over temp files, `dict` over real caches, `FakeGitDiff` over subprocess calls
- Avoid loading heavy dependencies in unit tests — mock at the boundary
- Isolate units so each test exercises one module, not the entire dependency graph
- Reset state between tests; never rely on test execution order

**Fast test patterns:**
- Protocol fakes over real implementations (see Protocol Fakes Over Mocks)
- Fixture scope: use `@pytest.fixture(scope="function")` as default; promote to session/class only when setup is expensive and stateless
- Skip slow tests by default: mark with `@pytest.mark.slow` and run via `pytest -m "not slow"` in CI fast paths
- Parallel-safe: structure tests so `pytest-xdist` works (no shared mutable state between tests)

### Protocol Fakes Over Mocks
Test dependencies are managed using simple fake implementations that satisfy protocols (e.g., `FakeGitDiff` for `GitDiffProvider`). This ensures tests break when interfaces change and avoids fragile standard mocks.

### Subagent Mocking Pattern
Orchestration logic is tested using a `FakeAssistantBackend` that simulates subagent responses, return codes, and file modifications. This enables exhaustive testing of retry loops and decision-making without hitting real APIs.

### Conflict Injection Pattern
The `doc-harmonizer` is verified by injecting known contradictions between SPEC, DESIGN, and PATTERNS. Tests confirm the harmonizer detects the conflict, identifies the higher-authority document, and proposes the correct resolution.

### Concurrency Stress Testing
The `.toml.lock` exclusive locking mechanism is verified using multiprocessing to simulate concurrent subagents. Tests ensure all updates are serialized and no data is lost.
