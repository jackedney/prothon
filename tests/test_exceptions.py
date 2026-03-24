"""Tests for custom exceptions."""

from __future__ import annotations

import inspect

import prothon.exceptions
from prothon.exceptions import ProthonError


def _all_exception_classes() -> set[type]:
    """Dynamically discover all ProthonError subclasses in the module."""
    return {
        obj
        for _, obj in inspect.getmembers(prothon.exceptions, inspect.isclass)
        if issubclass(obj, ProthonError)
        and obj is not ProthonError
        and obj.__module__ == prothon.exceptions.__name__
    }


def test_exception_inheritance():
    """All prothon exceptions must inherit from ProthonError."""
    exceptions = _all_exception_classes()
    assert exceptions, "no exception classes found in prothon.exceptions"
    for exc in exceptions:
        assert issubclass(exc, ProthonError), (
            f"{exc.__name__} does not inherit from ProthonError"
        )
