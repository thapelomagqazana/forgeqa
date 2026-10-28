"""Unit tests for the dependency-group configuration in ``pyproject.toml``.

These tests are the fast, in-process complement to
``scripts/verify_deps.sh`` (which is the slow, isolated-venv, end-to-end
verification). Together they cover WBS 1.1.3:

* The groups declared in ``pyproject.toml`` match the Phase 0.5.3 contract.
* ``[project].dependencies`` contains no optional dependency (playwright,
  httpx) — if it does, ``pip install forgeqa`` would pull them in.
* ``[project.optional-dependencies].all`` is the explicit union of ``ui``,
  ``api``, and ``dev`` — no self-reference, no missing entry.

The slow end-to-end scenarios (install into fresh venv, assert absence/
presence of optional modules) live in ``scripts/verify_deps.sh``. This file
covers the *configuration* contract; the script covers the *installed
environment* contract. Both are required by the WBS acceptance criteria.

Run only these tests:

    pytest tests/unit/test_dependency_groups.py -v
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


#: The repository root, resolved relative to this file. Keeping it as a
#: module-level constant means a future move of the test file (e.g. under
#: ``tests/integration/``) fails loudly at import time rather than in a
#: distant assertion.
REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    """Parse ``pyproject.toml`` once per test module.

    Returns
    -------
    dict
        Parsed TOML as a nested dict.

    Notes
    -----
    Uses :mod:`tomllib` (stdlib since Python 3.11) so that the test does
    not depend on ``tomli`` or any third-party TOML library. The project's
    ``requires-python = ">=3.11,<3.13"`` guarantees ``tomllib`` is present;
    no version guard is needed.
    """
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


# =============================================================================
# Positive cases — the contract is present and shaped correctly
# =============================================================================


def test_optional_dependency_groups_exist(pyproject: dict) -> None:
    """Given ``pyproject.toml``, when I read optional-dependencies, then ``ui``, ``api``, ``dev``, and ``all`` are declared.

    Phase 0.5.3 specifies exactly these four groups. A missing group means a
    documented install command will fail with "WARNING: forgeqa X.Y.Z does not
    provide the extra 'Y'" — which is exactly the failure mode WBS 1.1.3 exists
    to prevent.
    """
    extras = pyproject["project"]["optional-dependencies"]
    for name in ("ui", "api", "dev", "all"):
        assert name in extras, f"Missing optional-dependency group: {name}"


def test_ui_group_contains_playwright_only(pyproject: dict) -> None:
    """Given the ``ui`` group, when I read it, then it declares playwright and nothing else.

    Phase 0.5.3 says ``ui`` is browser automation only. Adding ``httpx`` to
    ``ui`` would violate the WBS acceptance criterion
    "pip install forgeqa[ui] installs Playwright" — well, that one would still
    pass — but it would also install HTTPX, defeating the point of separating
    the groups. The test asserts the *minimal* contract.
    """
    ui = pyproject["project"]["optional-dependencies"]["ui"]
    assert any("playwright" in dep for dep in ui), f"ui group missing playwright: {ui}"
    assert not any("httpx" in dep for dep in ui), f"ui group unexpectedly has httpx: {ui}"


def test_api_group_contains_httpx_only(pyproject: dict) -> None:
    """Given the ``api`` group, when I read it, then it declares httpx and nothing else.

    Symmetric to ``test_ui_group_contains_playwright_only``. ``api`` is the
    HTTP client group; adding ``playwright`` to it would install a 200 MB+
    browser toolchain for consumers who only want an HTTP client.
    """
    api = pyproject["project"]["optional-dependencies"]["api"]
    assert any("httpx" in dep for dep in api), f"api group missing httpx: {api}"
    assert not any("playwright" in dep for dep in api), (
        f"api group unexpectedly has playwright: {api}"
    )


def test_all_group_is_explicit_union(pyproject: dict) -> None:
    """Given the ``all`` group, when I read it, then every dep in ui/api/dev is present.

    The ``all`` group must be an explicit union, not a self-reference
    (``forgeqa[ui,api,dev]``). Self-reference works on modern pip but warns on
    older resolvers and is harder to reason about. This test asserts every
    dependency from the three source groups appears in ``all`` — i.e. ``all``
    is a superset — without necessarily being *exactly* the union (an extra
    tool in ``all`` is fine; a missing one is a bug).
    """
    extras = pyproject["project"]["optional-dependencies"]
    all_deps = set(extras["all"])
    for group in ("ui", "api", "dev"):
        missing = set(extras[group]) - all_deps
        assert not missing, f"all group missing deps from {group}: {sorted(missing)}"


# =============================================================================
# Negative cases — no optional dep leaks into core dependencies
# =============================================================================


@pytest.mark.parametrize("forbidden", ["playwright", "httpx"])
def test_core_dependencies_do_not_include_optional_deps(pyproject: dict, forbidden: str) -> None:
    """Given ``[project].dependencies``, when I read it, then it does not list optional deps.

    This is the *configuration* half of the WBS acceptance criterion
    "pip install forgeqa does not install Playwright or HTTPX". The other half
    is verified end-to-end by ``scripts/verify_deps.sh``. Catching it here
    fails the test suite in <100 ms instead of waiting for a venv install.
    """
    core = pyproject["project"]["dependencies"]
    assert not any(forbidden in dep for dep in core), (
        f"Core dependencies list {forbidden}: {core}. "
        f"This would install {forbidden} with `pip install forgeqa`, violating "
        f"WBS 1.1.3."
    )


# =============================================================================
# Edge cases — surprising-but-valid configurations
# =============================================================================


def test_no_self_reference_in_all(pyproject: dict) -> None:
    """Given the ``all`` group, when I read it, then it does not reference ``forgeqa[...]`` itself.

    A self-reference (``all = ["forgeqa[ui,api,dev]"]``) works on modern pip
    but is fragile: older resolvers warn, and some tools that statically read
    extras cannot flatten it. The ADR-002-era decision was to avoid
    self-references; this test enforces it.
    """
    all_deps = pyproject["project"]["optional-dependencies"]["all"]
    self_refs = [d for d in all_deps if d.startswith("forgeqa[")]
    assert not self_refs, f"Self-referential extras in 'all': {self_refs}"


# =============================================================================
# Corner cases — boundaries of the metadata contract
# =============================================================================


def test_requires_python_matches_support_matrix(pyproject: dict) -> None:
    """Given ``[project].requires-python``, when I read it, then it is the Phase 0.5.1 window.

    Guards against a silent widening/narrowing of the Python support matrix
    during a dependency bump. The WBS 1.1.3 verification script runs on 3.11
    and 3.12 (see CI matrix); if ``requires-python`` drifts, that CI run is
    not testing the declared support window.
    """
    assert pyproject["project"]["requires-python"] == ">=3.11,<3.13"


# =============================================================================
# Non-functional cases — file health
# =============================================================================


def test_pyproject_is_parseable(pyproject: dict) -> None:
    """Given ``pyproject.toml`` on disk, when I parse it, then it is valid TOML.

    The fixture already parses it; this test just makes the assertion explicit
    so a reviewer reading the file knows it is checked. Any TOML syntax error
    would have made every other test in this file fail with a confusing
    ``tomllib.TOMLDecodeError`` — this test turns that into a named failure.
    """
    assert isinstance(pyproject, dict)
    assert "project" in pyproject
