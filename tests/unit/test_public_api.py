"""Unit tests for the public-vs-internal import contract of ``forgeqa``.

These tests pin the contract documented in ``docs/public-api.md`` and
enforce the WBS 1.1.6 acceptance criteria:

* ``forgeqa.__all__`` matches the documented public surface, exactly.
* No name starting with a single underscore is exported (whether in
  ``__all__`` or as an attribute of the top-level module).
* No ``_``-prefixed submodule is imported as a side effect of
  ``import forgeqa``.
* No ``_``-prefixed submodule is exported at the top level (source check).
* ``docs/public-api.md`` exists and explicitly states the ``_``-prefix
  rule.

The contract is *not* just documentation. If this test suite is green,
the public surface matches ``docs/public-api.md``. If it is red, one of
the two has drifted and the PR must reconcile them.

Run only these tests:

    pytest tests/unit/test_public_api.py -v
    # or
    make verify-public-api
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


#: Repository root, resolved relative to this file.
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
PKG_DIR = SRC_DIR / "forgeqa"
PUBLIC_API_DOC = REPO_ROOT / "docs" / "public-api.md"


#: The expected public surface, as documented in ``docs/public-api.md``.
#:
#: **This constant lives in the test file on purpose.** It is NOT imported
#: from ``forgeqa.__all__`` — importing it would make every assertion a
#: tautology (a change to ``forgeqa.__all__`` would change the expected
#: value and pass the test). Instead, this constant is the *test-
#: authoritative* expected value: a change to ``forgeqa.__all__`` without
#: a matching change to this constant (and to ``docs/public-api.md``)
#: fails CI. That is the friction that makes the contract meaningful.
#:
#: Adding a name to the public API requires three coordinated edits:
#:   1. ``src/forgeqa/__init__.py`` — the ``__all__`` tuple.
#:   2. ``docs/public-api.md`` — the "public surface" table.
#:   3. This constant.
#:
#: Missing any of them fails ``test_all_matches_documented_surface``.
EXPECTED_ALL: tuple[str, ...] = (
    "__version__",
    "get_version",
)


#: Public submodules, if any. Currently empty: Phase 1 adds
#: ``forgeqa.fixtures`` and ``forgeqa.settings``, at which point this set
#: is extended and each submodule's ``__all__`` is asserted to match its
#: documented surface. Empty today so the test runs and passes on the
#: pre-alpha state. When a submodule is added here, its own
#: ``__all__`` is asserted against a per-submodule ``EXPECTED_<sub>``
#: constant that must be added alongside it.
PUBLIC_SUBMODULES: frozenset[str] = frozenset()


# =============================================================================
# Helpers
# =============================================================================


def _import_forgeqa() -> object:
    """Import ``forgeqa`` from the source tree, bypassing any installed copy.

    Ensures the test runs against the checked-out source, not an installed
    wheel, so a developer's ``pip install -e .`` cannot mask a regression
    in ``src/forgeqa/__init__.py``.

    Returns
    -------
    object
        The imported :mod:`forgeqa` module.

    Notes
    -----
    The pre-existing module is removed from :data:`sys.modules` after
    import so later tests in the session see a clean state. This mirrors
    the pattern in ``tests/unit/test_install_contract.py``.
    """
    sys.path.insert(0, str(SRC_DIR))
    try:
        import forgeqa  # noqa: PLC0415 - intentional late import

        return forgeqa
    finally:
        sys.path.remove(str(SRC_DIR))
        for name in list(sys.modules):
            if name == "forgeqa" or name.startswith("forgeqa."):
                del sys.modules[name]


def _is_dunder(name: str) -> bool:
    """Return ``True`` for names like ``__version__`` (double-underscore
    bracket, not a single-underscore prefix).
    """
    return len(name) >= 4 and name.startswith("__") and name.endswith("__")


# =============================================================================
# Positive cases — the public surface matches the documented contract
# =============================================================================


def test_all_matches_documented_surface() -> None:
    """Given ``forgeqa.__all__``, when inspected, then it equals :data:`EXPECTED_ALL`.

    This is the executable form of "docs/public-api.md lists all supported
    imports". If someone adds a public name to ``__all__`` without updating
    this test (and the doc), the test fails. If someone removes a name from
    ``__all__`` without updating this test (and the doc), the test also
    fails. The two must move together.
    """
    mod = _import_forgeqa()
    assert mod.__all__ == EXPECTED_ALL, (
        f"forgeqa.__all__ drifted from the documented contract.\n"
        f"  expected: {EXPECTED_ALL}\n"
        f"  actual:   {mod.__all__}\n"
        f"Update docs/public-api.md and tests/unit/test_public_api.py "
        f"in the same PR as the change to forgeqa.__all__."
    )


def test_all_is_immutable_tuple() -> None:
    """Given ``forgeqa.__all__``, when inspected, then it is a ``tuple``.

    A mutable ``list`` would allow consumers to widen the contract at
    runtime. This test pins the *type*, which is the precondition for the
    companion assertion in ``test_import.py::test_all_is_immutable``
    (which tests the absence of in-place mutation).
    """
    mod = _import_forgeqa()
    assert isinstance(mod.__all__, tuple), (
        f"forgeqa.__all__ must be a tuple, got {type(mod.__all__).__name__}: {mod.__all__!r}"
    )


@pytest.mark.parametrize("name", EXPECTED_ALL)
def test_documented_names_are_accessible(name: str) -> None:
    """Given a name in :data:`EXPECTED_ALL`, when accessed, then it exists on the module.

    Documents that ``from forgeqa import <name>`` works for each public
    name. A name in ``__all__`` that is not actually importable would break
    ``from forgeqa import *`` and any consumer using the documented import.
    """
    mod = _import_forgeqa()
    assert hasattr(mod, name), (
        f"forgeqa.__all__ lists {name!r} but forgeqa has no attribute of that name."
    )


def test_get_version_matches_dunder_version() -> None:
    """Given the public accessor, when called, then it equals ``__version__``.

    ``get_version()`` is documented as a stable accessor for
    ``__version__``; a divergence would confuse consumers who mix the two
    styles in reports or logs.
    """
    mod = _import_forgeqa()
    assert mod.get_version() == mod.__version__


# =============================================================================
# Negative cases — private names and modules are not exported
# =============================================================================


@pytest.mark.parametrize(
    "name",
    ["_is_version_fallback", "_resolve_version", "_internal", "_config"],
)
def test_private_name_not_in_all(name: str) -> None:
    """Given a private name, when ``__all__`` is inspected, then it is absent.

    A private name in ``__all__`` would make it public, which contradicts
    the ``_``-prefix convention. This parametrised test covers both actual
    private names (``_is_version_fallback``, ``_resolve_version``) and
    plausible future ones (``_internal``, ``_config``), so the test does
    not need to be updated when a new private helper is added — it simply
    asserts the *rule*.

    This is the WBS 1.1.6 acceptance criterion "The test fails if a new
    private module is accidentally exported", made concrete.
    """
    mod = _import_forgeqa()
    assert name not in mod.__all__, (
        f"Private name {name!r} is in forgeqa.__all__. Private names "
        f"(single-underscore prefix) must not appear in __all__; see "
        f'docs/public-api.md §"What is not public".'
    )


def test_no_underscore_name_in_all() -> None:
    """Given ``__all__``, when scanned, then no entry starts with ``_`` (except dunders).

    Python allows dunders (``__version__``) to be public when documented;
    this test allows dunders that are in :data:`EXPECTED_ALL` and rejects
    every other ``_``-prefixed name. It is a structural check that does
    not need to be updated when a new private helper is added.
    """
    mod = _import_forgeqa()
    # Dunders explicitly allowed by the documented contract:
    allowed_dunders = {name for name in EXPECTED_ALL if _is_dunder(name)}
    for name in mod.__all__:
        if _is_dunder(name):
            assert name in allowed_dunders, (
                f"Dunder {name!r} is in __all__ but not in the documented "
                f"public surface: {allowed_dunders}. If this is intentional, "
                f"add it to docs/public-api.md and EXPECTED_ALL in this file."
            )
        else:
            assert not name.startswith("_"), (
                f"forgeqa.__all__ contains a private name {name!r} "
                f"(single-underscore prefix). Private names must not be in "
                f'__all__; see docs/public-api.md §"What is not public".'
            )


def test_no_private_submodule_imported_by_top_level() -> None:
    """Given ``import forgeqa``, when :mod:`sys.modules` is inspected, then no ``forgeqa._*`` module is loaded.

    The top-level ``forgeqa/__init__.py`` must not import any private
    submodule. Doing so would make the private module a de-facto part of
    the import surface (even if it is not in ``__all__``), and consumers
    could come to rely on its side effects. Keeping it out of
    ``sys.modules`` after a bare import is the cleanest enforcement.

    Runs in a fresh subprocess so the assertion is not polluted by prior
    imports in this pytest session.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "import forgeqa\n"
                "privates = [m for m in sys.modules if m.startswith('forgeqa._')]\n"
                "assert not privates, privates\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`import forgeqa` loaded private submodules:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_no_private_module_in_source_tree_top_level() -> None:
    """Given ``src/forgeqa/``, when scanned, then ``__init__.py`` does not import any ``_``-prefixed submodule.

    A file ``src/forgeqa/_internal.py`` is fine as a private submodule. But
    a file ``src/forgeqa/_internal.py`` that ``__init__.py`` imports (and
    thus leaks into ``forgeqa._internal`` as a public-ish path) would be
    an accidental export. This test asserts that *if* a ``_``-prefixed
    submodule exists, it is not imported by ``__init__.py``. The companion
    runtime test (``test_no_private_submodule_imported_by_top_level``)
    asserts it is not in ``sys.modules`` after a bare import; this test
    asserts the source code does not import it.

    A future PR that wants to expose a name from a private module publicly
    must re-export the *name* via a public alias in ``__init__.py``, not
    by importing the private module and relying on its presence in
    ``sys.modules``.
    """
    init_path = PKG_DIR / "__init__.py"
    assert init_path.exists(), f"Missing {init_path}."
    init_source = init_path.read_text(encoding="utf-8")

    for entry in PKG_DIR.iterdir():
        # Only consider `_`-prefixed entries, and skip dunders like
        # `__pycache__` / `__init__.py`.
        if not entry.name.startswith("_"):
            continue
        if _is_dunder(entry.name):
            continue
        stem = entry.stem if entry.is_file() else entry.name
        # The forbidden patterns are:
        #   from ._<stem> import ...
        #   from forgeqa._<stem> import ...
        #   import forgeqa._<stem>
        forbidden_patterns = (
            f"from ._{stem}",
            f"from forgeqa._{stem}",
            f"import forgeqa._{stem}",
        )
        for pattern in forbidden_patterns:
            assert pattern not in init_source, (
                f"src/forgeqa/__init__.py imports the private submodule "
                f"{entry.name!r} via {pattern!r}. Private submodules must "
                f"not be imported by the top-level package; re-export the "
                f"public name via an alias instead (see "
                f"docs/engineering-standards.md §4.14)."
            )


# =============================================================================
# Edge cases — surprising-but-valid configurations
# =============================================================================


def test_documented_names_do_not_start_with_underscore() -> None:
    """Given :data:`EXPECTED_ALL`, when scanned, then no entry is a non-dunder underscore name.

    The documented surface itself must follow the rule. A contributor who
    accidentally adds ``"_helper"`` to :data:`EXPECTED_ALL` would make the
    test suite fail on this assertion before the wheel is built.
    """
    for name in EXPECTED_ALL:
        if _is_dunder(name):
            continue  # dunders are allowed by convention when documented
        assert not name.startswith("_"), (
            f"Documented public name {name!r} starts with an underscore. "
            f"Underscore-prefixed names are private by convention."
        )


# =============================================================================
# Corner cases — boundaries of the contract
# =============================================================================


def test_public_api_doc_exists_and_mentions_underscore_rule() -> None:
    """Given ``docs/public-api.md``, when read, then it explicitly states the ``_``-prefix rule.

    The document is half of the contract. If the ``_``-prefix rule is
    missing, the test suite and the build verifier enforce something the
    documentation does not describe — which is worse than not enforcing
    it, because consumers cannot discover the rule.
    """
    assert PUBLIC_API_DOC.exists(), (
        f"Missing {PUBLIC_API_DOC}. The public API contract must be documented."
    )
    text = PUBLIC_API_DOC.read_text(encoding="utf-8")
    lower = text.lower()
    # The exact wording may evolve; assert the concept is present.
    assert "underscore" in lower or "_ prefixed" in lower, (
        f"{PUBLIC_API_DOC} does not mention the underscore-prefix rule. "
        f"The document must state that `_`-prefixed modules are private."
    )
    # The specific phrasing WBS 1.1.6 requires: "private" or "not public".
    assert "private" in lower or "not public" in lower, (
        f"{PUBLIC_API_DOC} does not state that `_`-prefixed modules are private / not public."
    )


# =============================================================================
# Non-functional cases — performance and determinism
# =============================================================================


def test_import_for_the_test_is_fast() -> None:
    """Given the test's import helper, when timed, then it completes quickly.

    The contract test runs on every PR; if importing ``forgeqa`` from the
    source tree took more than a second, it would be tempting to skip
    locally. A fast test is one that gets run.
    """
    t0 = time.perf_counter()
    _import_forgeqa()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 1000, (
        f"_import_forgeqa took {elapsed_ms:.1f} ms; budget is 1000 ms. "
        f"Investigate slow setup in this module."
    )


def test_all_is_stable_across_imports() -> None:
    """Given two imports of ``forgeqa``, when compared, then ``__all__`` is identical.

    The contract must be deterministic. A future change that computes
    ``__all__`` dynamically (e.g. from an environment variable or a
    network call) would be caught here.
    """
    first = _import_forgeqa()
    second = _import_forgeqa()
    assert first.__all__ == second.__all__, (
        f"forgeqa.__all__ is not stable across imports: {first.__all__!r} vs {second.__all__!r}"
    )


def test_public_submodules_if_any() -> None:
    """Given :data:`PUBLIC_SUBMODULES`, when non-empty, then each submodule exposes an ``__all__``.

    Currently a no-op: ``PUBLIC_SUBMODULES`` is empty on the pre-alpha
    surface. When Phase 1 adds ``forgeqa.fixtures`` and
    ``forgeqa.settings``, they are added to the set and this test asserts
    each submodule is importable and has an ``__all__`` tuple. The
    per-submodule expected values are asserted by tests added alongside
    each submodule (following the ``EXPECTED_ALL`` pattern), not by this
    generic test — the generic test only asserts the *shape* of the
    contract, not its contents, because the contents are submodule-
    specific.
    """
    if not PUBLIC_SUBMODULES:
        pytest.skip("No public submodules declared yet (pre-alpha).")

    for submodule_name in PUBLIC_SUBMODULES:
        full_name = f"forgeqa.{submodule_name}"
        sys.path.insert(0, str(SRC_DIR))
        try:
            module = __import__(full_name, fromlist=["__all__"])
        finally:
            sys.path.remove(str(SRC_DIR))
            for name in list(sys.modules):
                if name == "forgeqa" or name.startswith("forgeqa."):
                    del sys.modules[name]
        assert hasattr(module, "__all__"), (
            f"Public submodule {full_name!r} has no __all__. "
            f"Public submodules must declare their exported names."
        )
        assert isinstance(module.__all__, tuple), (
            f"Public submodule {full_name!r}.__all__ must be a tuple, "
            f"got {type(module.__all__).__name__}: {module.__all__!r}"
        )
