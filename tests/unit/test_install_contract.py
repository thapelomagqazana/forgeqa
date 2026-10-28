"""Unit tests for the install-time contract of the packaged ``forgeqa``.

These tests are the fast, in-process complement to
``scripts/verify_install.sh`` (which is the slow, end-to-end verification:
build a wheel, install into a fresh venv, import from a temp cwd). Together
they cover WBS 1.1.5:

* ``forgeqa/__init__.py`` exposes the documented public surface
  (``__version__`` and ``get_version``) and nothing extra.
* ``forgeqa`` declares itself as typed (``py.typed`` marker).
* There is no ``sitecustomize.py``/``usercustomize.py`` that could break
  import isolation.
* The wheel contains no top-level ``tests`` or ``docs`` modules that would
  shadow real packages.

The slow end-to-end scenarios (install into fresh venv, prove import
resolves outside the source tree, run pytest from a temp cwd) live in
``scripts/verify_install.sh``. This file covers the *declaration* contract;
the script covers the *installed-environment* contract. Both are required.

Run only these tests:

    pytest tests/unit/test_install_contract.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


#: The repository root, resolved relative to this file.
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
PKG_DIR = SRC_DIR / "forgeqa"


# =============================================================================
# Positive cases — the package declares the public surface
# =============================================================================


def test_init_exposes_version_and_get_version() -> None:
    """Given ``src/forgeqa/__init__.py``, when imported, then ``__version__`` and ``get_version`` are exposed.

    These are the two names documented in ``docs/public-api.md``. A
    regression that removes either breaks consumers who rely on them for
    version reporting.
    """
    # Import via the source path to test the module itself, not the installed
    # distribution. The installed one is tested end-to-end by verify_install.sh.
    sys.path.insert(0, str(SRC_DIR))
    try:
        import forgeqa  # noqa: PLC0415 - intentional late import

        assert isinstance(forgeqa.__version__, str)
        assert forgeqa.__version__  # non-empty
        assert callable(forgeqa.get_version)
        assert forgeqa.get_version() == forgeqa.__version__
    finally:
        sys.path.remove(str(SRC_DIR))
        # Drop the cached module so subsequent tests in this session see the
        # installed distribution (if any) rather than the source-tree copy.
        for name in list(sys.modules):
            if name == "forgeqa" or name.startswith("forgeqa."):
                del sys.modules[name]


def test_init_all_matches_documented_surface() -> None:
    """Given ``__all__``, when inspected, then it matches the documented public surface.

    The expected surface is defined in ``tests/unit/test_public_api.py`` as
    ``EXPECTED_ALL``. Importing it here rather than duplicating the tuple
    means the two tests share a single source of truth: if a public name is
    added or removed, updating ``EXPECTED_ALL`` (and ``docs/public-api.md``
    and ``forgeqa.__all__``) is enough — this test does not need a parallel
    edit. Duplication of the *expected value* would be a maintenance trap.

    The test in ``test_public_api.py`` (``test_all_matches_documented_surface``)
    remains the authoritative one; this test is a fast sanity check that
    also runs as part of ``make test`` without needing the public-API
    test's subprocess work.
    """
    # Imported at call time (not module load) to keep this test independent
    # of collection order across the test suite.
    from tests.unit.test_public_api import EXPECTED_ALL  # noqa: PLC0415

    sys.path.insert(0, str(SRC_DIR))
    try:
        import forgeqa  # noqa: PLC0415

        assert forgeqa.__all__ == EXPECTED_ALL, (
            f"forgeqa.__all__ drifted from the documented surface.\n"
            f"  expected: {EXPECTED_ALL}\n"
            f"  actual:   {forgeqa.__all__}\n"
            f"Update docs/public-api.md, tests/unit/test_public_api.py's "
            f"EXPECTED_ALL, and src/forgeqa/__init__.py's __all__ in the "
            f"same PR."
        )
    finally:
        sys.path.remove(str(SRC_DIR))
        for name in list(sys.modules):
            if name == "forgeqa" or name.startswith("forgeqa."):
                del sys.modules[name]


# =============================================================================
# Negative cases — no accidental import hooks
# =============================================================================


@pytest.mark.parametrize("forbidden", ["sitecustomize", "usercustomize"])
def test_no_site_customization_modules(forbidden: str) -> None:
    """Given ``src/forgeqa/``, when scanned, then there is no ``<forbidden>.py``.

    A ``sitecustomize.py``/``usercustomize.py`` in the package would be
    imported automatically by the interpreter (Python's ``site`` module
    imports ``sitecustomize`` if present on ``sys.path``). If ``forgeqa``
    ever shipped one, it could mutate ``sys.path``, install import hooks,
    or otherwise break the isolation guarantees in
    ``docs/public-api.md`` §"Guarantees".

    This is a defensive check, not currently a real risk. It is here so
    that if someone adds such a file, the test suite fails and the
    contributor knows to ask whether it is intentional.
    """
    candidate = PKG_DIR / f"{forbidden}.py"
    assert not candidate.exists(), (
        f"Found {candidate}. A {forbidden}.py in the package would be "
        f"imported automatically by the interpreter and could break import "
        f"isolation. If this is intentional, update docs/public-api.md and "
        f"remove this test."
    )


# =============================================================================
# Edge cases — py.typed marker must be present for typed-package downstreams
# =============================================================================


def test_py_typed_marker_present() -> None:
    """Given ``src/forgeqa/``, when scanned, then ``py.typed`` exists.

    The ``Typing :: Typed`` PyPI classifier is a promise to downstream users
    that the package ships type information. PEP 561 requires a ``py.typed``
    marker in the package for mypy/pyright to consume inline types. Without
    it, consumers' type checkers ignore the package's annotations and fall
    back to ``Any`` — silently degrading their type safety.

    ``py.typed`` is created in the same commit that adds the classifier;
    this test enforces both together.
    """
    marker = PKG_DIR / "py.typed"
    assert marker.exists(), (
        f"Missing {marker}. The 'Typing :: Typed' classifier promises "
        f"downstream users that inline types are available; PEP 561 requires "
        f"the py.typed marker for that promise to be honoured."
    )
    # The marker should be empty (PEP 561); a non-empty marker is for
    # partial stubs, which we do not ship.
    assert marker.stat().st_size == 0, (
        f"{marker} must be empty per PEP 561 for an inline-typed package; "
        f"found {marker.stat().st_size} bytes. Partial-stub packages are a "
        f"different packaging decision that this ADR does not cover."
    )


# =============================================================================
# Corner cases — public names must not shadow stdlib
# =============================================================================


def test_public_names_do_not_shadow_stdlib() -> None:
    """Given ``forgeqa.__all__``, when inspected, then no name collides with a stdlib module.

    A name like ``json`` or ``typing`` in ``forgeqa.__all__`` would be
    importable via ``from forgeqa import *`` and could shadow the stdlib
    module of the same name in the consumer's namespace. This is a subtle
    footgun; the test catches it at config time before a consumer does.

    The stdlib module set is checked via ``sys.stdlib_module_names``,
    available on Python 3.10+ (the project floor is 3.11).
    """
    sys.path.insert(0, str(SRC_DIR))
    try:
        import forgeqa  # noqa: PLC0415

        stdlib = set(sys.stdlib_module_names)
        collisions = [name for name in forgeqa.__all__ if name in stdlib]
        assert not collisions, (
            f"forgeqa.__all__ contains names that shadow stdlib modules: "
            f"{collisions}. Rename them to avoid surprising consumers."
        )
    finally:
        sys.path.remove(str(SRC_DIR))
        for name in list(sys.modules):
            if name == "forgeqa" or name.startswith("forgeqa."):
                del sys.modules[name]


# =============================================================================
# Boundary cases — the packaging contract itself
# =============================================================================


def test_package_is_a_package_not_a_module() -> None:
    """Given ``src/forgeqa/``, when scanned, then it is a directory with ``__init__.py``.

    A module ``forgeqa.py`` instead of a package directory would still
    satisfy ``import forgeqa``, but it would prevent the submodule layout
    (``forgeqa.fixtures``, ``forgeqa.api``) that Phase 1 requires. This is a
    boundary check on the packaging decision itself, not on the current
    code.
    """
    assert PKG_DIR.is_dir(), f"Expected {PKG_DIR} to be a directory."
    init = PKG_DIR / "__init__.py"
    assert init.exists(), f"Expected {init} to exist."
    # A module would be a file named forgeqa.py in src/, not a directory.
    module_shadow = SRC_DIR / "forgeqa.py"
    assert not module_shadow.exists(), (
        f"Found {module_shadow}. A src-level forgeqa.py would shadow the "
        f"package directory; remove it."
    )


# =============================================================================
# Non-functional cases — pyproject.toml encoding
# =============================================================================


def test_pyproject_declares_typed_classifier() -> None:
    """Given ``pyproject.toml``, when read, then it declares ``Typing :: Typed``.

    The classifier and the ``py.typed`` marker must agree. This test pins
    the classifier side; ``test_py_typed_marker_present`` pins the file side.
    Together they prevent the "classifier says typed but marker missing"
    failure mode that silently degrades consumers' type checkers.
    """
    import tomllib  # noqa: PLC0415

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    classifiers = pyproject["project"]["classifiers"]
    assert "Typing :: Typed" in classifiers, f"'Typing :: Typed' classifier missing: {classifiers}"
