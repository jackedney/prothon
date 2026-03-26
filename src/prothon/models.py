"""Shared data models for the promise system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

PROMISE_PATH = Path("docs/change_promise.toml")


def _generate_id() -> str:
    """Generate a stable unique identifier for a task."""
    return uuid.uuid4().hex[:8]


@dataclass
class Task:
    """A single promised task within the change promise."""

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
    """Promise-level metadata (base commit, timestamps, etc.)."""

    base_commit: str = ""
    created_at: str = ""


@dataclass
class Promise:
    """Top-level change promise containing metadata and tasks."""

    metadata: Metadata = field(default_factory=Metadata)
    tasks: list[Task] = field(default_factory=list)
