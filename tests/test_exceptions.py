"""Tests for custom exceptions."""

from __future__ import annotations

from prothon.exceptions import (
    AssistantNotFoundError,
    ComplianceError,
    GitError,
    ProjectAlreadyInitError,
    ProjectNotFoundError,
    PromiseError,
    ProthonError,
    UnknownBackendError,
    VersionError,
)


def test_exception_inheritance():
    """All prothon exceptions must inherit from ProthonError."""
    exceptions = [
        ProjectNotFoundError,
        ProjectAlreadyInitError,
        PromiseError,
        AssistantNotFoundError,
        UnknownBackendError,
        ComplianceError,
        GitError,
        VersionError,
    ]
    for exc in exceptions:
        assert issubclass(exc, ProthonError)


def test_prothon_error_is_exception():
    """ProthonError must inherit from Exception."""
    assert issubclass(ProthonError, Exception)


def test_exception_instantiation():
    """Exceptions should be instantiable with a message."""
    msg = "test message"
    exc = ProthonError(msg)
    assert str(exc) == msg
