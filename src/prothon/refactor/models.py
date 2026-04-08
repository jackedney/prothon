from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DriftCategory(Enum):
    DESIGN_QUALITY = "design_quality"
    PATTERN_QUALITY = "pattern_quality"
    DOC_HIERARCHY = "doc_hierarchy"
    PATTERNS_COMPLIANCE = "patterns_compliance"
    LARGE_FILES = "large_files"
    MISSING_TESTS = "missing_tests"


class Severity(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PatternType(Enum):
    TRY_EXCEPT_FILE_IO = "try_except_file_io"
    PATH_EXISTS_GUARD = "path_exists_guard"


@dataclass
class DriftFinding:
    title: str
    rationale: str
    category: DriftCategory = DriftCategory.DOC_HIERARCHY
    severity: Severity = Severity.MEDIUM
    doc_sections: list[str] = field(default_factory=list)
    files_affected: list[Path] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class ModuleMetrics:
    path: Path
    line_count: int
    public_function_count: int
    import_count: int
    imported_by_count: int


@dataclass
class PatternOccurrence:
    pattern_type: PatternType
    file_path: Path
    line_number: int


@dataclass
class SimilarityGroup:
    function_name: str
    file_path: Path
    parameters: list[str]
