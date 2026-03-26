"""Custom exception hierarchy for prothon."""

from __future__ import annotations


class ProthonError(Exception):
    """Base for all prothon errors. CLI catches this for clean exit."""


class ProjectNotFoundError(ProthonError):
    """No prothon project root found walking up from cwd."""


class ProjectAlreadyInitError(ProthonError):
    """docs/SPEC.md already exists — project already initialized."""


class PromiseError(ProthonError):
    """Promise file missing, malformed, or task index out of range."""


class MaxAttemptsExceeded(PromiseError):
    """Task has reached its maximum retry attempts."""


class AssistantNotFoundError(ProthonError):
    """Assistant CLI binary not found on PATH."""


class UnknownBackendError(ProthonError):
    """Backend name not in registry."""


class ComplianceError(ProthonError):
    """Compliance check found failures."""


class GitError(ProthonError):
    """Git subprocess command failed."""


class VersionError(ProthonError):
    """Version string is malformed or bump operation failed."""
