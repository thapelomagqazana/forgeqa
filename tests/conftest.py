"""Shared pytest configuration and fixtures for ForgeQA's test suite.

Fixtures here are scoped narrowly to reduce cross-test coupling. Helpers that
tests import directly (rather than receiving via a fixture) live in
``tests/support.py``; this file is for pytest fixtures only, per pytest's
"conftest is not a library" guidance.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

import pytest

from tests.support import FORBIDDEN_IMPORTS_ON_TOP_LEVEL, run_isolated_python


@pytest.fixture(scope="session")
def forbidden_top_level_imports() -> tuple[str, ...]:
    """Return the list of modules forbidden from ``import forgeqa``.

    Returns
    -------
    tuple[str, ...]
        Top-level import names that must not appear in ``sys.modules`` after
        a bare ``import forgeqa``.
    """
    return FORBIDDEN_IMPORTS_ON_TOP_LEVEL


@pytest.fixture
def isolated_python() -> Callable[[str], subprocess.CompletedProcess[str]]:
    """Fixture wrapper around :func:`run_isolated_python` for ergonomic use.

    Returns
    -------
    Callable[[str], subprocess.CompletedProcess[str]]
        A callable that accepts a Python source string and returns the
        completed process.
    """
    return run_isolated_python
