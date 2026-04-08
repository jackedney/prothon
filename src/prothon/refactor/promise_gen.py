from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from prothon.git import rev_parse_head
from prothon.models import Metadata, Promise, Task
from prothon.refactor.models import DriftFinding


def generate_refactor_promise(root: Path, findings: list[DriftFinding]) -> Promise:
    base_commit = rev_parse_head(cwd=root)

    metadata = Metadata(
        base_commit=base_commit,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    sorted_findings = sorted(
        findings,
        key=lambda f: (
            bool(f.doc_sections),
            any("DESIGN.md" in s or "PATTERNS.md" in s for s in f.doc_sections),
        ),
        reverse=True,
    )

    tasks = []
    for finding in sorted_findings:
        files_to_modify = []
        files_to_create = []

        for f in finding.files_affected:
            try:
                rel_path = str(f.relative_to(root))
                if f.exists():
                    files_to_modify.append(rel_path)
                else:
                    files_to_create.append(rel_path)
            except ValueError:
                continue

        tasks.append(
            Task(
                title=finding.title,
                goal=finding.rationale,
                success_criteria=f"Resolve the drift identified: {finding.title}",
                files_to_modify=files_to_modify,
                files_to_create=files_to_create,
                doc_sections=finding.doc_sections,
            )
        )

    return Promise(metadata=metadata, tasks=tasks)
